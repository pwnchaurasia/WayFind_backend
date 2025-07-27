from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import DeviceInfo


class DeviceInfoService:
    @staticmethod
    def update_device_info(db: Session, user_id: UUID, device_data: dict) -> DeviceInfo:
        # First, mark all other devices as inactive for this user
        db.query(DeviceInfo).filter(
            DeviceInfo.user_id == user_id,
            DeviceInfo.device_id != device_data['device_id']
        ).update({"is_current_device": False})

        # Try to find existing device
        existing_device = db.query(DeviceInfo).filter(
            DeviceInfo.user_id == user_id,
            DeviceInfo.device_id == device_data['device_id']
        ).first()

        if existing_device:
            # Update existing device
            for key, value in device_data.items():
                setattr(existing_device, key, value)
            existing_device.is_current_device = True
            existing_device.last_active_at = func.now()
            db.commit()
            db.refresh(existing_device)
            return existing_device
        else:
            # Create new device
            device_info = DeviceInfo(
                user_id=user_id,
                is_current_device=True,
                **device_data
            )
            db.add(device_info)
            db.commit()
            db.refresh(device_info)
            return device_info

    @staticmethod
    def get_current_device(db: Session, user_id: UUID) -> Optional[DeviceInfo]:
        return db.query(DeviceInfo).filter(
            DeviceInfo.user_id == user_id,
            DeviceInfo.is_current_device == True
        ).first()