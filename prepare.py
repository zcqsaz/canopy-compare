"""Build the offline archive review data and a matched historical prioritization check."""
import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from PIL import Image
from scipy.stats import norm


ROOT = Path(__file__).resolve().parent
MODEL = ROOT / 'model'
META = 'https://raw.githubusercontent.com/eco4cast/neon4cast-targets/9d3adbaf4e3486b76661dcc96dc1b5109018d8d6/NEON_Field_Site_Metadata_20220412.csv'
DEMOS = [pd.Timestamp('2025-05-08'), pd.Timestamp('2025-10-09')]
CHANNELS = ['gcc_90', 'rcc_90']
Z80 = norm.ppf(.80)


def history_at(obs, site, channel, date):
    history = obs[(site, channel)].loc[date-pd.Timedelta(days=35):date-pd.Timedelta(days=2)].dropna()
    if history.empty:
        return history, None
    last = history.index[-1]
    baseline = history.loc[last-pd.Timedelta(days=3):].median()
    return history, float(baseline)


def images(bundle):
    jobs = []
    for issue, sites in bundle['issues'].items():
        for site, site_data in sites.items():
            dates = [s['obs'][-1][0] for s in site_data.values() if s['obs']]
            if not dates:
                continue
            jobs.append((f'{issue}/{site}',site,pd.Timestamp(min(dates))))
            for lookahead in range(1,8):
                target = pd.Timestamp(issue)+pd.Timedelta(days=lookahead)
                jobs.append((f'{issue}/{site}/{target.date()}',site,target))
    previous_path=ROOT/'data'/'images.json'
    previous=json.loads(previous_path.read_text()) if previous_path.exists() else {}
    def fetch_one(job):
        key,site,day=job
        if key in previous and (ROOT/previous[key]['file']).exists():
            return key,previous[key]
        camera = bundle['sites'][site]['camera']
        url = f'https://phenocam.nau.edu/webcam/browse/{camera}/{day:%Y/%m/%d}/'
        index = requests.get(url, timeout=25)
        index.raise_for_status()
        links = [a['href'] for a in BeautifulSoup(index.content, 'html.parser').select('a[href]')
                 if re.search(r'/data/archive/.*_\d{6}\.jpg$', a['href'])]
        unique = sorted(set(links))
        if not unique:
            return key,None
        def minutes(path):
            t = path.split('_')[-1]
            return abs(int(t[:2])*60+int(t[2:4])-720)
        original = urljoin(url, min(unique, key=minutes))
        photo = requests.get(original, timeout=25)
        photo.raise_for_status()
        name = f'{site}-{day.date()}.jpg'
        img = Image.open(io.BytesIO(photo.content)).convert('RGB')
        img.thumbnail((640, 480))
        img.save(ROOT/'images'/name, quality=84, optimize=True)
        return key,{'file':'images/'+name, 'date':str(day.date()), 'original':original,
            'local_time':original[-10:-8]+':'+original[-8:-6], 'original_sha256':hashlib.sha256(photo.content).hexdigest()}
    with ThreadPoolExecutor(max_workers=3) as pool:
        manifest={key:entry for key,entry in pool.map(fetch_one,jobs) if entry}
    (ROOT/'data'/'images.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', action='store_true', help='Refresh near-noon archive images')
    args = parser.parse_args()
    data = ROOT/'data'
    retro = pd.read_parquet(MODEL/'retrospective_forecasts.parquet').reset_index(drop=True)
    raw = pd.read_csv(MODEL/'phenology-targets.csv.gz',parse_dates=['datetime'])
    raw['datetime'] = raw.datetime.dt.tz_localize(None)
    observations = raw.pivot(index='datetime',columns=['site_id','variable'],values='observation').sort_index()
    sites = sorted(retro.site_id.unique())
    meta_file = data/'sites.csv'
    columns = ['field_site_id','field_site_name','field_site_state','phenocam_vegetation','phenocam_roi','phenocam_code','field_latitude','field_longitude','neon_url']
    if not meta_file.exists():
        source = pd.read_csv(META,usecols=columns)
        source[source.field_site_id.isin(sites)].to_csv(meta_file,index=False)
    meta = pd.read_csv(meta_file).set_index('field_site_id')
    bundle = {'sites':{},'issues':{}}
    for site in sites:
        row = meta.loc[site]
        bundle['sites'][site] = {'name':row.field_site_name.removesuffix(' NEON'),'state':row.field_site_state,
            'vegetation':row.phenocam_vegetation,'roi':row.phenocam_roi,'camera':row.phenocam_code,
            'latitude':round(row.field_latitude,4),'longitude':round(row.field_longitude,4),'url':row.neon_url}
    for issue in DEMOS:
        panel = retro[(retro.issue==issue)&(retro.datetime<=issue+pd.Timedelta(days=7))]
        group = {}
        for (site,channel), frame in panel.groupby(['site_id','variable']):
            past, base = history_at(observations,site,channel,issue)
            frame = frame.sort_values('datetime')
            group.setdefault(site,{})[channel] = {'obs':[[str(d.date()),round(float(v),6)] for d,v in past.items()],
                'base':base, 'fc':[[str(r.datetime.date()),round(r.model,7),round(r.model_sd,7),
                     None if pd.isna(r.truth) else round(r.truth,6)] for r in frame.itertuples()]}
        bundle['issues'][str(issue.date())] = group

    # The outcome table contains rows with a verifying observation. Retain only
    # complete seven-day site panels for the matched week-planning comparison.
    checks = []
    scored = retro[(retro.datetime-retro.issue).dt.days.between(1,7)]
    for (issue,site,channel), f in scored.groupby(['issue','site_id','variable']):
        if len(f)!=7:
            continue
        past,base = history_at(observations,site,channel,issue)
        if base is None or (issue-past.index[-1]).days>7:
            continue
        end=past.index[-1]
        previous=past.loc[end-pd.Timedelta(days=10):end-pd.Timedelta(days=7)].median()
        if pd.isna(previous):
            continue
        f=f.sort_values('datetime')
        # Predicted direction is chosen before verification. The control chooses
        # the largest absolute week-over-week trend, then checks on day seven.
        ix=(abs(f.model-base)-Z80*f.model_sd).idxmax()
        pick=f.loc[ix]
        magnitude_pick=f.loc[(f.model-base).abs().idxmax()]
        checks.append({'issue':str(issue.date()),'site':site,'channel':channel,'rank':abs(pick.model-base)-Z80*pick.model_sd,
            'target':str(pick.datetime.date()),'delta':abs(pick.truth-base),'trend':abs(base-previous),
            'trend_delta':abs(f.iloc[-1].truth-base),'day7_rank':abs(f.iloc[-1].model-base)-Z80*f.iloc[-1].model_sd,
            'unadjusted_rank':abs(magnitude_pick.model-base),'unadjusted_delta':abs(magnitude_pick.truth-base),
            'selected_hit':bool((pick.truth-base)*np.sign(pick.model-base)>=.010),
            'trend_hit':bool((f.iloc[-1].truth-base)*np.sign(base-previous)>=.010)})
    table=pd.DataFrame(checks)
    table.to_csv(ROOT/'evidence'/'decision_panel.csv',index=False)
    results=[]
    for (issue,channel),g in table.groupby(['issue','channel']):
        if len(g)<6:
            continue
        for method,order,value in [('planner','rank','delta'),('recent trend','trend','trend_delta'),('planner, fixed day 7','day7_rank','trend_delta'),('mean change alone','unadjusted_rank','unadjusted_delta')]:
            chosen=g.sort_values([order,'site'],ascending=[False,True]).head(3)
            results.append({'issue':issue,'channel':channel,'method':method,'eligible':len(g),
                'mean_shift':chosen[value].mean(),'fraction_over_threshold':(chosen[value]>=.01).mean()})
    result=pd.DataFrame(results)
    summary=[]
    for (channel,method),g in result.groupby(['channel','method']):
        summary.append({'channel':channel,'method':method,'issues':len(g),'picks':3*len(g),
            'mean_shift':round(g.mean_shift.mean(),5),'hit_rate':round(g.fraction_over_threshold.mean(),4)})
    coverage={}
    for channel,g in retro.groupby('variable'):
        coverage[channel]=round((abs(g.truth-g.model)<=norm.ppf(.9)*g.model_sd).mean(),4)
    bundle['validation']={'decision':summary,'coverage':coverage,'forecast':json.loads((MODEL/'verification.json').read_text())['backtests']}
    (ROOT/'evidence'/'decision_validation.json').write_text(json.dumps(bundle['validation'],indent=2),encoding='utf-8')
    if args.images:
        images(bundle)
    photo_file=data/'images.json'
    bundle['images']=json.loads(photo_file.read_text()) if photo_file.exists() else {}
    (data/'bundle.js').write_text('window.CANOPY = '+json.dumps(bundle,ensure_ascii=False,separators=(',',':'),allow_nan=False)+';\n',encoding='utf-8')
    print(json.dumps({'cases':summary,'coverage':coverage,'photos':len(bundle['images'])},indent=2))


if __name__=='__main__':
    main()
