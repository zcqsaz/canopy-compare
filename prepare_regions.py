"""Match archive frames to official PhenoCam vegetation masks using measured midday RGB."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

for name in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[name]="1"

import numpy as np
import requests
from PIL import Image, ImageFilter

ROOT=Path(__file__).resolve().parent


def csv_rows(raw):
    return list(csv.DictReader(line for line in raw.decode("utf-8-sig").splitlines() if line and not line.startswith("#")))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache",type=Path,required=True,help="Directory for original images, TIFFs and upstream CSVs")
    args=p.parse_args()
    args.cache.mkdir(parents=True,exist_ok=True)
    session=requests.Session()
    def fetch(url):
        path=args.cache/(hashlib.sha256(url.encode()).hexdigest()[:12]+"-"+url.rsplit("/",1)[-1])
        if not path.is_file():
            response=session.get(url,timeout=(8,35))
            response.raise_for_status()
            path.write_bytes(response.content)
        return path.read_bytes()

    photos=json.loads((ROOT/"data/images.json").read_text(encoding="utf-8"))
    sites=csv_rows((ROOT/"data/sites.csv").read_bytes())
    region_dir=ROOT/"images/regions"
    region_dir.mkdir(exist_ok=True)
    output={"frames":{},"masks":{},"sources":{}}
    for s in sites:
        code=s["field_site_id"]; camera=s["phenocam_code"]; roi=s["phenocam_roi"]
        entries=[e for k,e in photos.items() if k.split("/")[1]==code]
        if not entries:continue
        base=f"https://phenocam.nau.edu/data/archive/{camera}/ROI/"
        stem=f"{camera}_{roi}_"
        files={"daily":base+stem+"1day.csv","registry":base+stem+"roi.csv"}
        sources={k:fetch(u) for k,u in files.items()}
        output["sources"][code]={k:{"url":u,"sha256":hashlib.sha256(sources[k]).hexdigest()} for k,u in files.items()}
        days={r["date"]:r for r in csv_rows(sources["daily"])}
        registry=csv_rows(sources["registry"])
        masks={}
        for record in entries:
            filename=Path(urlsplit(record["original"]).path).name
            date=record["date"]; local=record["file"]
            row=days.get(date)
            result={"date":date,"site":code,"roi":roi,"filename":filename}
            output["frames"][local]=result
            if not row or row["midday_filename"]!=filename:
                result["status"]="archive frame differs from published midday frame"
                continue
            reported=[row["midday_"+c] for c in "rgb"]
            if any(x in ("NA","NaN","") for x in reported):
                result["status"]="published midday colour unavailable"
                continue
            ref=np.asarray(reported,dtype=float)
            clock=filename.rsplit("_",1)[-1][:6]
            stamp=f"{date} {clock[:2]}:{clock[2:4]}:{clock[4:6]}"
            valid=[r["maskfile"] for r in registry if r["start_date"]+" "+r["start_time"]<=stamp<=r["end_date"]+" "+r["end_time"]]
            if not valid:
                result["status"]="no dated mask in the camera registry"
                continue
            full=fetch(record["original"])
            if hashlib.sha256(full).hexdigest()!=record["original_sha256"]:
                raise ValueError(f"Source photograph has changed: {filename}")
            rgb=np.asarray(Image.open(io.BytesIO(full)).convert("RGB"))
            matches=[]
            for name in sorted(set(valid)):
                if name not in masks:
                    raw=fetch(base+name)
                    image=np.asarray(Image.open(io.BytesIO(raw)).convert("L"))
                    if not set(np.unique(image)).issubset({0,255}):
                        raise ValueError(f"Unknown mask encoding for {name}")
                    masks[name]=image==0,hashlib.sha256(raw).hexdigest()
                mask,digest=masks[name]
                if mask.shape!=rgb.shape[:2] or not mask.any():continue
                means=rgb[mask].mean(axis=0)
                matches.append((float(np.max(np.abs(means-ref))),name,means))
            matches.sort(key=lambda x:x[0])
            # A match must reproduce all three published channels within one 8-bit count.
            # Ambiguity stays visible if two masks both reproduce those published values.
            result["published_rgb"]=[float(x) for x in ref]
            result["candidate_count"]=len(matches)
            result["whole_frame_max_rgb_error"]=round(float(np.max(np.abs(rgb.reshape(-1,3).mean(axis=0)-ref))),6)
            if len(matches)>1:
                result["next_mask_max_rgb_error"]=round(matches[1][0],6)
            acceptable=[x for x in matches if x[0]<=1.0]
            if len(acceptable)!=1:
                result["status"]="multiple matching masks" if acceptable else "published colour could not be reproduced"
                continue
            error,name,means=acceptable[0]; mask,digest=masks[name]
            result.update(status="verified",mask=name,rgb=[round(float(x),6) for x in means],
                          max_rgb_error=round(error,6))
            if name not in output["masks"]:
                overlay=f"images/regions/{Path(name).stem}.png"
                sample=Image.open(ROOT/local)
                mb=Image.fromarray(mask.astype("uint8")*255).resize(sample.size,Image.Resampling.NEAREST)
                values=np.asarray(mb)
                inner=np.asarray(mb.filter(ImageFilter.MinFilter(3)))
                outer=np.asarray(mb.filter(ImageFilter.MaxFilter(3)))
                rgba=np.zeros((*values.shape,4),dtype="uint8")
                rgba[values==0]=[12,23,23,100]
                rgba[(outer!=values)]=[25,43,43,255]
                rgba[(inner!=values)]=[255,235,124,255]
                Image.fromarray(rgba).save(ROOT/overlay,optimize=True)
                output["masks"][name]={"overlay":overlay,"source":base+name,"sha256":digest,
                    "fraction":round(float(mask.mean()),6),"size":[mask.shape[1],mask.shape[0]],"roi":roi}
        validated=sum(r["status"]=="verified" for r in output["frames"].values() if r["site"]==code)
        print(f"{code}: {validated}/{len(entries)} images matched",flush=True)
    serialized=json.dumps(output,indent=1,ensure_ascii=True,allow_nan=False)
    (ROOT/"data/regions.js").write_text("window.CANOPY_REGIONS="+serialized+";\n",encoding="utf-8")
    verified=[r for r in output["frames"].values() if r["status"]=="verified"]
    region_errors=np.asarray([r["max_rgb_error"] for r in verified])
    whole_errors=np.asarray([r["whole_frame_max_rgb_error"] for r in verified])
    status={key:sum(r["status"]==key for r in output["frames"].values()) for key in sorted({r["status"] for r in output["frames"].values()})}
    audit={"archived_photos":len(output["frames"]),"sites":len(output["sources"]),"status_counts":status,
           "matched_sites":len({r["site"] for r in verified}),"unique_matched_masks":len(output["masks"]),
           "multiple_candidates_uniquely_resolved":sum(r["candidate_count"]>1 for r in verified),
           "comparison":"For the same verified photos, maximum absolute error across published PhenoCam midday R/G/B means in 8-bit channel units.",
           "matched_mask_median_error":float(np.median(region_errors)),"matched_mask_largest_error":float(region_errors.max()),
           "whole_photo_median_error":float(np.median(whole_errors)),"whole_photo_within_one_count":int((whole_errors<=1).sum()),
           "verification_rule":"Exact midday source filename and original SHA-256; same dimensions as a dated binary mask; exactly one candidate within one count for all three channels."}
    (ROOT/"evidence/region_verification.json").write_text(json.dumps(audit,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(audit),flush=True)


if __name__=="__main__":
    main()
