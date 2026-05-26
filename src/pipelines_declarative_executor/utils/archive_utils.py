import os, logging


class ArchiveUtils:
    @staticmethod
    def archive(pipeline_dir: str, target_path: str, fail_on_missing: bool = False, use_sops_key: bool = False):
        if not os.path.exists(pipeline_dir):
            logging.warning(f"Trying to archive non-existent path: \"{pipeline_dir}\"")
            if fail_on_missing:
                raise ValueError("Nothing present at provided path")
            else:
                return

        import subprocess
        if use_sops_key and (sops_age_key := os.getenv('SOPS_AGE_KEY')):
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
    def unarchive(archive_path: str, target_path: str, fail_on_missing: bool = False, use_sops_key: bool = False):
        if not os.path.exists(archive_path):
            logging.warning(f"Trying to unarchive non-existent path: \"{archive_path}\"")
            if fail_on_missing:
                raise ValueError("Nothing present at provided path")
            else:
                return

        import subprocess
        if use_sops_key and (sops_age_key := os.getenv('SOPS_AGE_KEY')):
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
    def backup_directory(source_dir: str, target_dir: str, excluded_dirs: list = None):
        import zipfile
        from datetime import datetime
        from pathlib import Path
        from pipelines_declarative_executor.utils.constants import Constants

        backup_name = "backup_" + datetime.now().strftime("%d_%m_%Y_%H_%M_%S_%f") + ".zip"
        backup_path = Path(target_dir) / backup_name
        Path(target_dir).mkdir(parents=True, exist_ok=True)

        if excluded_dirs is None:
            excluded_dirs = [Constants.PIPELINE_BACKUP_DIR_NAME, Constants.PIPELINE_DEBUG_DIR_NAME]
        with zipfile.ZipFile(str(backup_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_dir):
                for excluded_dir in excluded_dirs:
                    if excluded_dir in dirs:
                        dirs.remove(excluded_dir)
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    zf.write(file_path, arcname)
