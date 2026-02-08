
@router.post("/{ride_id}/stop", name="end_ride_api")
async def end_ride_api(
    ride_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """End ride (API - Mobile)"""
    try:
        ride = db.query(Ride).filter(Ride.id == ride_id).first()
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")

        # Check permissions
        # 1. Org Admin
        is_admin = False
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == ride.organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_([OrganizationRole.FOUNDER, OrganizationRole.CO_FOUNDER, OrganizationRole.ADMIN]),
            OrganizationMember.is_active == True,
            OrganizationMember.is_deleted == False
        ).first()
        
        if membership or current_user.role == UserRole.SUPER_ADMIN:
            is_admin = True
            
        # 2. Ride Lead (Creator/Lead Participant)
        is_lead = False
        lead_participant = db.query(RideParticipant).filter(
            RideParticipant.ride_id == ride.id,
            RideParticipant.user_id == current_user.id,
            RideParticipant.role == ParticipantRole.LEAD
        ).first()
        
        if lead_participant:
            is_lead = True
            
        if not is_admin and not is_lead:
             raise HTTPException(status_code=403, detail="Only Admins or Ride Leads can end a ride")

        if ride.status != RideStatus.ACTIVE:
             raise HTTPException(status_code=400, detail="Ride is not active")

        # End ride
        ride.status = RideStatus.COMPLETED
        ride.ended_at = datetime.now(timezone.utc)
        
        # Log activity
        from db.models import RideActivity
        activity = RideActivity(
            ride_id=ride.id,
            user_id=current_user.id,
            activity_type=ActivityType.RIDE_ENDED,
            message=f"🏁 Ride ended by {current_user.name}"
        )
        db.add(activity)

        db.commit()

        logger.info(f"Ride {ride_id} ended (API) by {current_user.id}")

        return {
            "status": "success",
            "message": "Ride ended successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error ending ride api: {e}")
        raise HTTPException(status_code=500, detail="Failed to end ride")
