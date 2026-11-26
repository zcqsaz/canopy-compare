"""Thirty-day PhenoCam forecasts with historical seasonal analogues and recent canopy colour."""
import argparse
import json
import os
from pathlib import Path
import warnings

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

import numpy as np
import pandas as pd
from scipy.special import ndtr
from sklearn.ensemble import HistGradientBoostingRegressor


ROOT = Path(__file__).resolve().parent
VARS = ("gcc_90", "rcc_90")
STEPS = np.arange(1, 31)
MODEL_ID = "canopy_analog"
FEATURES = ["horizon","site","channel","sin_doy","cos_doy","current","older","month",
            "trend","season","season_spread","season_now","analog","offset","hybrid","other_channel","age"]


def examples(obs, day, indices, latency):
    asof = (day - indices[0]).days
    block = obs[max(0, asof-latency-36):asof-latency+1]
    recent = np.flatnonzero(np.isfinite(block[:, 0]) & np.isfinite(block[:, 1]))
    if not len(recent):
        return []
    last = max(0, asof-latency-36) + recent[-1]
    if asof - last > 12:
        return []
    # Same calendar day in available earlier years, with neighbouring phase offsets.
    past = np.array([((day-pd.DateOffset(years=years))-indices[0]).days
                     for years in range(1, day.year-indices[0].year+1)])
    shifts = np.arange(-12, 13, 3)
    anchors = (past[:, None] + shifts).ravel()
    phase_shift = np.tile(shifts, len(past))
    keep = (anchors >= 40) & (anchors+30 < asof-latency)
    anchors, phase_shift = anchors[keep], phase_shift[keep]
    if len(anchors)<12:
        return []
    offsets = np.arange(-26,-latency+1,2)
    current_history = obs[asof+offsets]
    past_history = obs[anchors[:,None]+offsets]
    scale = np.maximum(np.nanstd(past_history, axis=(0,1)), .006)
    diff = (past_history - current_history[None,:,:])/scale
    valid = np.isfinite(diff).sum(axis=(1,2))
    distance = np.nansum(diff**2,axis=(1,2))/np.maximum(valid,1)
    weights = np.exp(-np.minimum(distance,40) / .85 - (phase_shift/12)**2/2)
    weights[valid<6] = 0
    ahead = obs[anchors[:,None]+STEPS]
    available = np.isfinite(ahead)
    weighted = np.where(available,ahead,0)*weights[:,None,None]
    denom = (available*weights[:,None,None]).sum(axis=0)
    season = np.nanmean(ahead,axis=0)
    spread = np.nanstd(ahead,axis=0)
    analog = np.divide(weighted.sum(axis=0),denom,out=season.copy(),where=denom>0)
    c = np.nanmedian(obs[max(0,last-3):last+1],axis=0)
    old = np.nanmedian(obs[max(0,last-13):last-6],axis=0)
    month = np.nanmedian(obs[max(0,last-32):last-14],axis=0)
    old = np.where(np.isfinite(old),old,c)
    season_now = np.nanmean(obs[anchors-(asof-last)],axis=0)
    obs_window = obs[last-3:last+1]
    if not np.isfinite(obs_window).any() or not np.isfinite(season).any():
        return []
    dates = day+pd.to_timedelta(STEPS, unit="D")
    angle = dates.dayofyear.to_numpy()*2*np.pi/365.25
    rows = []
    for j,var in enumerate(VARS):
        hybrid = (.5*season[:,j]+.5*analog[:,j]+(c[j]-season_now[j])*np.exp(-STEPS/14))
        truth = np.full(30,np.nan)
        valid_steps = asof+STEPS<len(obs)
        truth[valid_steps] = obs[asof+STEPS[valid_steps],j]
        rows.append(pd.DataFrame(dict(issue=day,datetime=dates,variable=var,horizon=STEPS,
                     sin_doy=np.sin(angle),cos_doy=np.cos(angle),channel=j,current=c[j],older=old[j],
                     month=month[j],trend=c[j]-old[j],season=season[:,j],season_spread=spread[:,j],
                     season_now=season_now[j],analog=analog[:,j],offset=c[j]-season_now[j],hybrid=hybrid,
                     other_channel=c[1-j],age=asof-last,truth=truth)))
    return rows


def scales(cal, col):
    sq = (cal[col]-cal.truth)**2
    counts = sq.groupby([cal.site,cal.channel,cal.horizon]).size()
    errsum = sq.groupby([cal.site,cal.channel,cal.horizon]).sum()
    pooled = sq.groupby([cal.channel,cal.horizon]).mean()
    prior = [pooled.loc[(c,h)] for _,c,h in counts.index]
    return np.sqrt((errsum+12*np.array(prior))/(counts+12)).clip(lower=.001)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue",default="2026-11-26")
    args=parser.parse_args()
    issue=pd.Timestamp(args.issue)
    source=pd.read_csv(ROOT/"phenology-targets.csv.gz",parse_dates=["datetime"])
    source["datetime"]=source.datetime.dt.tz_localize(None)
    source=source[(source.datetime<=issue-pd.Timedelta(days=2)) & source.observation.notna()]
    latest=source.groupby("site_id").datetime.max()
    # Prospective eligibility uses current data availability, independent of performance.
    sites=sorted(latest.index[latest >= issue-pd.Timedelta(days=7)])
    index=pd.date_range(source.datetime.min(),issue)
    origins=list(pd.date_range("2019-01-10",issue-pd.Timedelta(days=30),freq="14D"))+[issue]
    frames=[]
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore",message="Mean of empty slice|All-NaN slice encountered|Degrees of freedom")
        for i,name in enumerate(sites):
            grid=source.query("site_id==@name").pivot(index="datetime",columns="variable",values="observation")
            obs=grid.reindex(index=index,columns=VARS).to_numpy()
            parts=[d for t in origins for d in examples(obs,t,index,latency=2)]
            if parts:
                df=pd.concat(parts,ignore_index=True);df["site"]=i;df["site_id"]=name;frames.append(df)
    allrows=pd.concat(frames,ignore_index=True)
    rows=allrows.dropna(subset=["truth","current","season","hybrid"]).copy()
    train=rows[rows.datetime<"2023-01-01"]
    estimator=HistGradientBoostingRegressor(max_iter=160,max_leaf_nodes=15,min_samples_leaf=90,
                 learning_rate=.08,l2_regularization=1,early_stopping=False,random_state=115)
    estimator.fit(train[FEATURES],train.truth-train.hybrid)
    evalrows=allrows[(allrows.issue>="2023-01-01") & allrows.hybrid.notna()].copy()
    evalrows["model"]=evalrows.hybrid+estimator.predict(evalrows[FEATURES])
    cal=evalrows[(evalrows.issue.dt.year==2023)&(evalrows.datetime.dt.year==2023)].dropna(subset=["truth"])
    evalrows=evalrows.set_index(["site","channel","horizon"],drop=False)
    labels=["model","current","season"]
    for method in labels:
        calibrated=scales(cal,method)
        fallback=(cal[method]-cal.truth).std()
        evalrows[method+"_sd"]=calibrated.reindex(evalrows.index).fillna(fallback).to_numpy()
    verified=evalrows[(evalrows.issue>="2024-01-01") & evalrows.truth.notna()]
    verified[["issue","datetime","site_id","variable","truth","model","model_sd"]].to_parquet(
        ROOT/"retrospective_forecasts.parquet",index=False)
    report={"issue":str(issue.date()),"sites_selected_on_recent_observations":sites,
            "train_rows":len(train),"calibration_rows":len(cal),"backtests":{}}
    for year in (2024,2025,2026):
        idx=(evalrows.issue.dt.year==year)&(evalrows.datetime.dt.year==year)
        sample=evalrows[idx].dropna(subset=["truth"])
        stats={"sites":int(sample.site.nunique()),"origins":int(sample.issue.nunique()),"values":len(sample)}
        for method in labels:
            e=(sample.truth-sample[method]).to_numpy()
            sd=sample[method+"_sd"].to_numpy();z=e/sd
            crps=sd*(z*(2*ndtr(z)-1)+np.sqrt(2/np.pi)*np.exp(-z*z/2)-1/np.sqrt(np.pi))
            stats[method]={"crps":float(crps.mean()),"mae":float(np.abs(e).mean())}
        report["backtests"][str(year)]=stats
    future=evalrows[evalrows.issue==issue].copy().reset_index(drop=True)
    future["project_id"]="neon4cast";future["model_id"]=MODEL_ID
    future["reference_datetime"]=str(issue.date());future["family"]="normal"
    future["datetime"]=future.datetime.dt.strftime("%Y-%m-%d")
    output=[]
    for code,param in (("model","mu"),("model_sd","sigma")):
        part=future[["project_id","model_id","datetime","reference_datetime","site_id","family","variable"]].copy()
        part["parameter"]=param;part["prediction"]=future[code].to_numpy();output.append(part)
    forecasts=pd.concat(output,ignore_index=True)
    forecasts.to_csv(ROOT/f"phenology-{issue.date()}-{MODEL_ID}.csv",index=False)
    report["forecast_rows"]=len(forecasts)
    (ROOT/"verification.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print(json.dumps(report,indent=2),flush=True)


if __name__=="__main__":
    main()
