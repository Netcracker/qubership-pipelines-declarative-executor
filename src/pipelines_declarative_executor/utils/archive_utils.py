import os, subprocess, shutil

from datetime import datetime
from pathlib import Path


class ArchiveUtils:
    @staticmethod
    def archive(pipeline_dir: str, target_path: str):
        if sops_age_key := os.getenv('SOPS_AGE_KEY'):
            subprocess.run(
                ['7z', 'a', '-tzip', '-p', target_path, pipeline_dir],
                input=sops_age_key,
                capture_output=True,
                text=True,
                check=True
            )
        else:
            subprocess.run(
                ['7z', 'a', '-tzip', target_path, pipeline_dir],
                capture_output=True,
                text=True,
                check=True
            )

    @staticmethod
    def unarchive(archive_path: str, target_path: str):
        if sops_age_key := os.getenv('SOPS_AGE_KEY'):
            subprocess.run(
                ['7z', 'x', f'-o{target_path}', archive_path],
                input=sops_age_key,
                capture_output=True,
                text=True,
                check=True
            )
        else:
            subprocess.run(
                ['7z', 'x', f'-o{target_path}', archive_path],
                capture_output=True,
                text=True,
                check=True,
            )

    @staticmethod
    def backup_directory(source_dir: str, target_dir: str):
        backup_name = "backup_" + datetime.now().strftime("%d_%m_%Y_%H_%M_%S_%f")
        shutil.make_archive(backup_name, 'zip', source_dir)
        backup_name = backup_name + ".zip"
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        shutil.move(backup_name, Path(target_dir).joinpath(backup_name))
