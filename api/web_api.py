import os
from uuid import UUID
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from db.db_conn import get_db
from db.models import Organization, Ride
from utils.templates import jinja_templates
from utils.dependencies import get_current_user_web

router = APIRouter()

@router.get("/.well-known/assetlinks.json")
async def asset_links():
    # TODO: REPLACE WITH ACTUAL SHA256 FINGERPRINT FROM PLAY CONSOLE / KEYSTORE
    return [{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "com.luciferthelight.squadra",
            "sha256_cert_fingerprints": ["FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:7C:4E:58:BF:14:0E:51:75:A8:86:16:79:A8:11:AB:F5"] 
        }
    }]

@router.get("/.well-known/apple-app-site-association")
async def apple_links():
    return {
        "applinks": {
            "apps": [],
            "details": [{"appID": "YOUR_TEAM_ID.com.luciferthelight.squadra", "paths": ["/join/*"]}]
        }
    }

@router.get("/join/org/{join_code}")
async def web_join_org(request: Request, join_code: str, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.join_code == join_code).first()
    if not org:
        return jinja_templates.TemplateResponse("error.html", {"request": request, "error": "Organization not found"})
    
    return jinja_templates.TemplateResponse(
        "organization/join_org.html", 
        {
            "request": request, 
            "organization": org, 
            "join_code": join_code
        }
    )

@router.get("/join/ride/{ride_id}")
async def web_join_ride(
    request: Request, 
    ride_id: UUID, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_web)
):
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
             return jinja_templates.TemplateResponse("error.html", {"request": request, "error": "Ride not found"})
        
        # We pass empty vehicles list if not logged in, as this page is primarily for App Redirection
        return jinja_templates.TemplateResponse(
            "ride/join_ride.html", 
            {
                "request": request, 
                "ride": ride, 
                "user": current_user, 
                "vehicles": [] 
            }
        )
    except Exception as e:
        return jinja_templates.TemplateResponse("error.html", {"request": request, "error": str(e)})
