"""Exercise the shipping offline interface in an isolated headless renderer."""
import csv
import hashlib
import json
import io
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def main():
    checks={}
    with sync_playwright() as runtime:
        render=runtime.chromium.launch(headless=True,args=['--disable-gpu'])
        page=render.new_page(viewport={'width':1440,'height':900},locale='en-GB')
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((ROOT/'index.html').as_uri())
        def picked():
            return page.locator('.row[aria-pressed=true]').get_attribute('data-site')
        def export(screenshot=None):
            with page.expect_download() as received:
                page.locator('#download').click()
            contents=Path(received.value.path()).read_bytes()
            if screenshot:page.screenshot(path=ROOT/'evidence'/screenshot)
            page.locator('#sheet button').click()
            return contents
        original=export()
        parsed=list(csv.DictReader(io.StringIO(original.decode())))
        assert [r['site'] for r in parsed]==['STEI','UKFS','TREE']
        assert all(r['visual_review']=='Unreviewed' and r['before_image'].endswith('.jpg') and r['after_image'].endswith('.jpg') for r in parsed)
        checks['spring_green']={'rows':parsed,'sha256':hashlib.sha256(original).hexdigest()}
        page.locator('#compare').click()
        assert page.locator('.region-photo img:not(.region-overlay)').count()==2
        assert all(page.locator('.region-photo img:not(.region-overlay)').evaluate_all('(imgs) => imgs.map(i=>i.complete && i.naturalWidth>0)'))
        page.screenshot(path=ROOT/'evidence'/'spring-pair.png')
        page.locator('#show-region').check()
        pairs=page.locator('.region-photo').evaluate_all("""boxes=>boxes.map(box=>{
          const [photo,overlay]=box.querySelectorAll('img');
          const a=photo.getBoundingClientRect(),b=overlay.getBoundingClientRect();
          return overlay.complete && overlay.naturalWidth>0 && !overlay.hidden &&
            ['left','top','width','height'].every(k=>Math.abs(a[k]-b[k])<0.5);
        })""")
        assert pairs==[True,True] and page.locator('.region-note:visible a').count()==2
        assert not page.locator('#outcome').count()
        page.screenshot(path=ROOT/'evidence'/'measured-region.png')
        page.locator('#show-region').uncheck()
        assert page.locator('.region-overlay:visible').count()==0
        checks['official_camera_regions']={'spring_masks_aligned':pairs,'later_outcome_hidden':True,
                                           'source_links':2,'toggle_returns_original':True}
        page.select_option('#review-mark','Colour change visible');page.locator('#sheet button').click()
        page.reload(); page.locator('#compare').click()
        assert page.locator('#review-mark').input_value()=='Colour change visible'
        page.locator('#sheet button').click()
        marked=export('review-log.png')
        assert list(csv.DictReader(io.StringIO(marked.decode())))[0]['visual_review']=='Colour change visible'
        assert export()==marked
        checks['repeat_and_persistence']={'identical_csv':True,'mark_after_reload':True}
        before=page.locator('#rows').inner_text();page.locator('#reveal').check()
        assert '0.446' in page.locator('#outcome').inner_text() and before==page.locator('#rows').inner_text()
        checks['spring_known_outcome']=page.locator('#outcome').inner_text()
        page.select_option('#issue','2025-10-09');page.select_option('#channel','rcc_90')
        assert picked()=='TREE'
        page.locator('#reveal').check()
        assert '0.515' in page.locator('#outcome').inner_text() and '−0.083' in page.locator('#outcome').inner_text()
        page.locator('#outcome').scroll_into_view_if_needed();page.screenshot(path=ROOT/'evidence'/'autumn-miss.png')
        checks['autumn_wrong_direction']={'top':picked(),'actual':page.locator('#outcome').inner_text()}
        page.select_option('#budget','14')
        large=list(csv.DictReader(io.StringIO(export().decode())))
        assert len(large)>=12
        assert all(r['after_image'].endswith('.jpg') and r['before_image'].endswith('.jpg') for r in large)
        checks['all_autumn_pairs']={'count':len(large),'sites':[r['site'] for r in large]}
        page.locator('#end').fill('2025-11-01');page.locator('#end').dispatch_event('change');assert page.locator('#download').is_disabled()
        checks['date_out_of_range']=page.locator('#detail h2').inner_text()
        page.locator('#restore').click();assert picked()=='TREE'
        page.locator('#search').fill('unlisted camera');assert page.locator('#download').is_disabled()
        checks['search_no_match']=page.locator('#detail h2').inner_text();page.locator('#restore').click()
        page.select_option('#issue','2025-05-08');page.select_option('#channel','gcc_90');page.locator('#compare').click()
        assert page.locator('#review-mark').input_value()=='Colour change visible'
        page.locator('#sheet button').click()
        checks['previous_mark_survives_errors']=True
        hidden_independence=page.evaluate('''()=>{const altered=structuredClone(window.CANOPY);Object.values(altered.issues).forEach(p=>Object.values(p).forEach(site=>Object.values(site).forEach(s=>s.fc.forEach(row=>row[3]=0))));return plan(altered,options()).rows.map(r=>r.code+' '+r.date).join()===plan(window.CANOPY,options()).rows.map(r=>r.code+' '+r.date).join();}''');assert hidden_independence
        checks['changed_all_outcomes_replay']={'ranks_dates_unchanged':hidden_independence}
        removed=page.evaluate('''()=>{const altered=structuredClone(window.CANOPY);const opts=options();const r=plan(altered,opts).rows[0];delete altered.images[opts.issue+'/'+r.code+'/'+r.date];return plan(altered,opts).rows.every(v=>v.code!==r.code||v.date!==r.date);}''');assert removed
        checks['missing_photo_excluded']=removed
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        page.locator('#view-evidence').click();assert page.get_by_text('Three image pairs per issue').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        checks['mobile']={'width':390,'horizontal_overflow':False}
        page.close()
        blocked=render.new_page();blocked.add_init_script("Object.defineProperty(window,'localStorage',{get:()=>{throw new Error('storage unavailable')}})");blocked.goto((ROOT/'index.html').as_uri());blocked.locator('#compare').click();blocked.select_option('#review-mark','Image obscured or uncertain');assert 'Session only' in blocked.locator('#marked').inner_text();blocked.locator('#sheet button').click()
        with blocked.expect_download() as saved:blocked.locator('#download').click()
        assert 'Image obscured or uncertain' in Path(saved.value.path()).read_text();checks['storage_disabled_export']=True;blocked.close()
        assert not errors;checks['uncaught_javascript_errors']=errors
        render.close()
    (ROOT/'evidence'/'ui_checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    print('Passed:',', '.join(checks))


if __name__=='__main__':
    main()
