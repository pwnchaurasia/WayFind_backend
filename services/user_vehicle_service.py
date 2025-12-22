from sqlalchemy.orm import Session
from db.models import UserRideInformation, User
from db.schemas import CreateVehicle, VehicleResponse
from utils import app_logger


class UserVehicleService:
    
    @staticmethod
    def create_vehicle(user: User, vehicle_data: CreateVehicle, db: Session):
        """Create new vehicle for user"""
        try:
            vehicle = UserRideInformation(
                user_id=user.id,
                make=vehicle_data.make,
                model=vehicle_data.model,
                year=vehicle_data.year,
                license_plate=vehicle_data.license_plate,
                is_primary=vehicle_data.is_primary,
                is_pillion=vehicle_data.is_pillion
            )
            db.add(vehicle)
            db.commit()
            db.refresh(vehicle)
            
            logger.info(f"Vehicle created for user: {user.id} - {vehicle.make} {vehicle.model}")
            return VehicleResponse.from_orm(vehicle)
            
        except Exception as e:
            logger.exception(f"Error creating vehicle: {e}")
            raise e
    
    @staticmethod
    def get_user_vehicles(user: User, db: Session):
        """Get all vehicles for user"""
        try:
            vehicles = db.query(UserRideInformation).filter(
                UserRideInformation.user_id == user.id
            ).all()
            
            return [VehicleResponse.from_orm(vehicle) for vehicle in vehicles]
            
        except Exception as e:
            logger.exception(f"Error getting user vehicles: {e}")
            raise e
    
    @staticmethod
    def update_vehicle(vehicle_id: str, user: User, vehicle_data: CreateVehicle, db: Session):
        """Update vehicle"""
        try:
            vehicle = db.query(UserRideInformation).filter(UserRideInformation.id == vehicle_id).first()
            if not vehicle:
                raise Exception("Vehicle not found")
            
            if vehicle.user_id != user.id:
                raise Exception("You can only update your own vehicles")
            
            # Update fields
            if vehicle_data.make:
                vehicle.make = vehicle_data.make
            if vehicle_data.model:
                vehicle.model = vehicle_data.model
            if vehicle_data.year:
                vehicle.year = vehicle_data.year
            if vehicle_data.license_plate:
                vehicle.license_plate = vehicle_data.license_plate
            if vehicle_data.is_primary is not None:
                vehicle.is_primary = vehicle_data.is_primary
            if vehicle_data.is_pillion is not None:
                vehicle.is_pillion = vehicle_data.is_pillion
            
            db.commit()
            db.refresh(vehicle)
            
            logger.info(f"Vehicle updated: {vehicle_id}")
            return VehicleResponse.from_orm(vehicle)
            
        except Exception as e:
            logger.exception(f"Error updating vehicle: {e}")
            raise e
    
    @staticmethod
    def delete_vehicle(vehicle_id: str, user: User, db: Session):
        """Delete vehicle"""
        try:
            vehicle = db.query(UserRideInformation).filter(UserRideInformation.id == vehicle_id).first()
            if not vehicle:
                raise Exception("Vehicle not found")
            
            if vehicle.user_id != user.id:
                raise Exception("You can only delete your own vehicles")
            
            db.delete(vehicle)
            db.commit()
            
            logger.info(f"Vehicle deleted: {vehicle_id}")
            return {"status": "success", "message": "Vehicle deleted successfully"}
            
        except Exception as e:
            logger.exception(f"Error deleting vehicle: {e}")
            raise e
    
    @staticmethod
    def set_primary_vehicle(user: User, vehicle_id: str, db: Session):
        """Set vehicle as primary"""
        try:
            vehicle = db.query(UserRideInformation).filter(UserRideInformation.id == vehicle_id).first()
            if not vehicle:
                raise Exception("Vehicle not found")
            
            if vehicle.user_id != user.id:
                raise Exception("You can only manage your own vehicles")
            
            # Unset all other vehicles as primary
            db.query(UserRideInformation).filter(
                UserRideInformation.user_id == user.id,
                UserRideInformation.id != vehicle_id
            ).update({"is_primary": False})
            
            # Set this vehicle as primary
            vehicle.is_primary = True
            db.commit()
            
            logger.info(f"Vehicle set as primary: {vehicle_id}")
            return VehicleResponse.from_orm(vehicle)
            
        except Exception as e:
            logger.exception(f"Error setting primary vehicle: {e}")
            raise e
