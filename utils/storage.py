from abc import ABC, abstractmethod
from typing import Optional, Tuple
from fastapi import UploadFile
import os
import uuid
import shutil
from utils.app_logger import createLogger

logger = createLogger("storage")


class StorageProvider(ABC):
    @abstractmethod
    async def upload_logo(self, file: UploadFile) -> Tuple[bool, Optional[str], Optional[str]]:
        """Upload logo. Returns: (success, logo_url, error_message)"""
        pass

    @abstractmethod
    def delete_logo(self, logo_url: str) -> bool:
        """Delete logo. Returns: success"""
        pass


class LocalStorage(StorageProvider):
    """Store files locally on server"""

    def __init__(self):
        self.upload_dir = "uploads/logos"
        os.makedirs(self.upload_dir, exist_ok=True)

    async def upload_logo(self, file: UploadFile) -> Tuple[bool, Optional[str], Optional[str]]:
        try:
            # Validate file type
            if not file.content_type.startswith('image/'):
                return False, None, "Only image files are allowed"

            # Validate file size (400KB max)
            content = await file.read()
            file_size_kb = len(content) / 1024

            if file_size_kb > 400:
                return False, None, f"File too large ({file_size_kb:.0f}KB). Max 400KB allowed"

            # Generate unique filename
            file_extension = file.filename.split('.')[-1].lower()
            allowed_extensions = ['jpg', 'jpeg', 'png', 'webp', 'gif']

            if file_extension not in allowed_extensions:
                return False, None, f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"

            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            file_path = os.path.join(self.upload_dir, unique_filename)

            # Save file
            with open(file_path, 'wb') as f:
                f.write(content)

            logo_url = f"/uploads/logos/{unique_filename}"
            logger.info(f"Logo uploaded locally: {logo_url}")
            return True, logo_url, None

        except Exception as e:
            logger.exception(f"Error uploading logo: {e}")
            return False, None, str(e)

    def delete_logo(self, logo_url: str) -> bool:
        try:
            if not logo_url:
                return True

            # Extract filename from URL
            filename = logo_url.split('/')[-1]
            file_path = os.path.join(self.upload_dir, filename)

            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Logo deleted: {logo_url}")

            return True

        except Exception as e:
            logger.exception(f"Error deleting logo: {e}")
            return False


# Easy switching: Change this line to switch providers
storage = LocalStorage()

# Later, when you want to switch to cloud storage:
# from utils.cloud_storage import CloudflareR2Storage
# storage = CloudflareR2Storage()