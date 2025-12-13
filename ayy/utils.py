import uuid
import os


def user_photo_upload_path(instance, filename):
    """
    Upload path for user photos on the local server:
    media/user_photos/<user_id>/<uuid>.<ext>
    """
    ext = filename.split('.')[-1]  # get file extension
    filename = f"{uuid.uuid4()}.{ext}"  # rename to UUID to avoid collisions
    return os.path.join('user_photos', str(instance.user.id), filename)


def dynamic_upload_path(instance, filename):
    # Determine the folder based on the related foreign key
    if instance.inv:
        folder = 'inv_files'
    else:
        folder = 'expspv_files'

    # Build the upload path
    return os.path.join(folder, filename)
