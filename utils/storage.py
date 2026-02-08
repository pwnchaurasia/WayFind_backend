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
    async def upload_avatar(self, file: UploadFile) -> Tuple[bool, Optional[str], Optional[str]]:
        """Upload avatar. Returns: (success, avatar_url, error_message)"""
        pass

    @abstractmethod
    def delete_logo(self, logo_url: str) -> bool:
        """Delete logo. Returns: success"""
        pass


class LocalStorage(StorageProvider):
    """Store files locally on server"""

    def __init__(self):
        self.logo_dir = "uploads/logos"
        self.avatar_dir = "uploads/avatars"
        os.makedirs(self.logo_dir, exist_ok=True)
        os.makedirs(self.avatar_dir, exist_ok=True)

    async def _upload_file(self, file: UploadFile, directory: str, max_size_kb: int = 5000, prefix: str = "uploads") -> Tuple[bool, Optional[str], Optional[str]]:
        try:
            # Validate file type
            if not file.content_type.startswith('image/'):
                return False, None, "Only image files are allowed"

            # Validate file size
            content = await file.read()
            file_size_kb = len(content) / 1024

            if file_size_kb > max_size_kb:
                return False, None, f"File too large ({file_size_kb:.0f}KB). Max {max_size_kb}KB allowed"

            # Generate unique filename
            file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else 'jpg'
            allowed_extensions = ['jpg', 'jpeg', 'png', 'webp', 'gif']

            if file_extension not in allowed_extensions:
                return False, None, f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"

            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            file_path = os.path.join(directory, unique_filename)

            # Save file
            with open(file_path, 'wb') as f:
                f.write(content)

            # Return URL relative to server root (e.g. /uploads/avatars/abc.jpg)
            # Assuming "uploads" is mounted at root
            subdir = os.path.basename(directory)
            file_url = f"/{prefix}/{subdir}/{unique_filename}"
            logger.info(f"File uploaded locally: {file_url}")
            return True, file_url, None

        except Exception as e:
            logger.exception(f"Error uploading file: {e}")
            return False, None, str(e)

    async def upload_logo(self, file: UploadFile) -> Tuple[bool, Optional[str], Optional[str]]:
        return await self._upload_file(file, self.logo_dir, max_size_kb=400)

    async def upload_avatar(self, file: UploadFile) -> Tuple[bool, Optional[str], Optional[str]]:
        return await self._upload_file(file, self.avatar_dir, max_size_kb=5000)

    def delete_logo(self, logo_url: str) -> bool:
        try:
            if not logo_url:
                return True

            # Extract filename from URL
            filename = logo_url.split('/')[-1]
            file_path = os.path.join(self.logo_dir, filename)

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