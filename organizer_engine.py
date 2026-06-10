import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Default category keyword mappings
DEFAULT_RULES = {
    "Kicks": ["kick", "kik", "bd"],
    "Snares": ["snare", "snr", "sd"],
    "Claps": ["clap", "clp", "snap"],
    "Hi-Hats": ["hat", "hihat", "hh", "oh", "ch", "openhat", "closedhat"],
    "Toms": ["tom"],
    "Cymbals": ["cymbal", "crash", "ride", "splash", "china"],
    "Bass & 808s": ["808", "bass", "sub"],
    "Vocals & Vox": ["vocal", "vox", "chant", "singing"],
    "FX & Textures": ["fx", "sfx", "sweep", "riser", "fall", "noise", "texture"],
    "Melodic & Stabs": ["synth", "pluck", "loop", "melody", "chord", "stab", "piano", "keys", "pad", "lead", "guitar", "bell"],
    "Percussion": ["perc", "percussion", "shaker", "rim", "cowbell", "cabasa", "woodblock", "bongo", "conga", "guiro"]
}

# The order in which we check categories. More specific categories should be checked first.
CATEGORY_PRIORITY = [
    "Kicks",
    "Snares",
    "Claps",
    "Hi-Hats",
    "Toms",
    "Cymbals",
    "Bass & 808s",
    "Vocals & Vox",
    "FX & Textures",
    "Melodic & Stabs",
    "Percussion"
]

AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".aif", ".aiff", ".m4a"}

class AudioClassifier:
    def __init__(self, rules_path: Optional[Path] = None):
        self.rules_path = rules_path
        self.rules = self.load_rules()

    def load_rules(self) -> Dict[str, List[str]]:
        """Load rules from file, falling back to defaults if not found or invalid."""
        if self.rules_path and self.rules_path.exists():
            try:
                with open(self.rules_path, 'r', encoding='utf-8') as f:
                    rules = json.load(f)
                    # Verify structure
                    if isinstance(rules, dict):
                        return {k: [w.lower() for w in v] for k, v in rules.items()}
            except Exception as e:
                print(f"Error loading rules from {self.rules_path}: {e}. Using defaults.")
        
        # Return deep copy of defaults
        return {k: [w.lower() for w in v] for k, v in DEFAULT_RULES.items()}

    def save_rules(self, rules: Dict[str, List[str]]) -> bool:
        """Save rules to file."""
        if not self.rules_path:
            return False
        try:
            self.rules = {k: [w.lower().strip() for w in v if w.strip()] for k, v in rules.items()}
            with open(self.rules_path, 'w', encoding='utf-8') as f:
                json.dump(self.rules, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving rules: {e}")
            return False

    def classify(self, file_path: Path) -> str:
        """Classify a file based on its name."""
        filename_lower = file_path.name.lower()
        
        # Check each category in priority order
        for category in CATEGORY_PRIORITY:
            keywords = self.rules.get(category, [])
            for kw in keywords:
                # To prevent matching sub-strings that aren't words, we could do basic split analysis.
                # However, simple substring matching is standard for audio kit filenames like 'Kick01.wav' or '808Bass.wav'.
                if kw in filename_lower:
                    return category
                    
        return "Uncategorized"


class OrganizerEngine:
    def __init__(self, classifier: AudioClassifier):
        self.classifier = classifier

    def scan_directory(self, base_dir: Path, recursive: bool = True) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Scans a base directory. Returns a nested dictionary:
        {
            "subfolder_relative_path": {
                "category_name": [
                    {
                        "name": "Kick_01.wav",
                        "full_path": "E:/Kits/Sub/Kick_01.wav",
                        "size": 102456,
                        "detected_category": "Kicks"
                    }
                ]
            }
        }
        """
        results = {}
        base_path = Path(base_dir).resolve()
        
        if not base_path.exists() or not base_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {base_path}")

        # If base directory has direct subfolders, we want to treat each immediate subfolder
        # as a separate "kit" group. If files are at the root, they go into a special "." group.
        
        for root, dirs, files in os.walk(base_path):
            root_path = Path(root).resolve()
            
            # Calculate relative path from base_dir to grouping folder
            # If we are in the root directory, group is "."
            # If we are in a subdirectory, the group name is the name of the immediate subdirectory of base_path.
            # E.g. base_path = E:\Kits, root = E:\Kits\Kit A\Kicks, relative_to_base = Kit A\Kicks.
            # We want to group by the direct subfolders of the main folder.
            # E.g. Group = "Kit A"
            
            if root_path == base_path:
                group_name = "."
            else:
                # Get the first folder segment after base_path
                relative = root_path.relative_to(base_path)
                group_name = str(relative.parts[0])

            # Filter for audio files
            audio_files = [f for f in files if Path(f).suffix.lower() in AUDIO_EXTENSIONS]
            if not audio_files:
                continue

            if group_name not in results:
                results[group_name] = {}

            for file in audio_files:
                file_path = root_path / file
                category = self.classifier.classify(file_path)
                
                if category not in results[group_name]:
                    results[group_name][category] = []
                
                try:
                    file_size = file_path.stat().st_size
                except Exception:
                    file_size = 0
                    
                results[group_name][category].append({
                    "name": file,
                    "full_path": str(file_path),
                    "size": file_size,
                    "relative_root": str(root_path.relative_to(base_path)),
                    "detected_category": category
                })

            if not recursive:
                # Stop os.walk from recursing further
                dirs.clear()

        return results

    def organize(
        self, 
        base_dir: Path, 
        scan_results: Dict[str, Dict[str, List[Dict]]], 
        copy_mode: bool = False, 
        consolidate_mode: bool = False,
        progress_callback = None
    ) -> List[Tuple[str, str, bool, str]]:
        """
        Performs the physical organization.
        
        If consolidate_mode is True:
        It moves/copies the files from all subfolders into main sound category folders 
        at the root of base_dir (e.g. base_dir/Kicks). Filenames are prefixed with the original 
        subfolder name to retain context and prevent collisions.
        
        If consolidate_mode is False (In-Place):
        It moves/copies the files into category folders inside each individual subfolder 
        (e.g. base_dir/KitName/Kicks).
        
        Returns a list of operations: (src_path, dest_path, success, message)
        """
        base_path = Path(base_dir).resolve()
        operations_log = []
        
        # Calculate total files for progress tracking
        total_files = sum(
            len(files) 
            for group, cats in scan_results.items() 
            for cat, files in cats.items()
        )
        processed_files = 0

        for group_name, categories in scan_results.items():
            # Find the root folder for this group
            if consolidate_mode:
                group_root = base_path
            else:
                group_root = base_path if group_name == "." else base_path / group_name

            for category, file_list in categories.items():

                # Define target directory
                target_dir = group_root / category
                
                # Create directory if it doesn't exist
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    msg = f"Failed to create directory {target_dir}: {e}"
                    print(msg)
                    for file_info in file_list:
                        operations_log.append((file_info["full_path"], "", False, msg))
                        processed_files += 1
                        if progress_callback:
                            progress_callback(processed_files, total_files)
                    continue

                for file_info in file_list:
                    src_path = Path(file_info["full_path"])
                    
                    # Prefix file name with original folder name in consolidate mode to avoid conflicts
                    if consolidate_mode and group_name != ".":
                        dest_name = f"{group_name} - {file_info['name']}"
                    else:
                        dest_name = file_info["name"]
                        
                    dest_path = target_dir / dest_name
                    
                    # Prevent moving file into itself
                    if src_path.resolve() == dest_path.resolve():
                        operations_log.append((str(src_path), str(dest_path), True, "Already in place"))
                        processed_files += 1
                        if progress_callback:
                            progress_callback(processed_files, total_files)
                        continue

                    # If destination exists, generate a unique name
                    if dest_path.exists():
                        base = dest_path.stem
                        ext = dest_path.suffix
                        counter = 1
                        while (target_dir / f"{base}_{counter}{ext}").exists():
                            counter += 1
                        dest_path = target_dir / f"{base}_{counter}{ext}"

                    try:
                        if copy_mode:
                            shutil.copy2(src_path, dest_path)
                            op_name = "Copied"
                        else:
                            shutil.move(src_path, dest_path)
                            op_name = "Moved"
                            
                        operations_log.append((str(src_path), str(dest_path), True, f"{op_name} successfully"))
                    except Exception as e:
                        operations_log.append((str(src_path), str(dest_path), False, f"Error: {e}"))

                    processed_files += 1
                    if progress_callback:
                        progress_callback(processed_files, total_files)

        return operations_log

    def undo_organization(self, history_data: Dict, progress_callback = None) -> List[Tuple[str, str, bool, str]]:
        """
        Undoes a previous organization run based on history data.
        
        Returns a list of undo operations: (dest_path, src_path, success, message)
        """
        operations = history_data.get("operations", [])
        copy_mode = history_data.get("copy_mode", False)
        
        total_ops = len(operations)
        processed_ops = 0
        undo_log = []
        
        # Process in reverse order
        for op in reversed(operations):
            if not op.get("success", False):
                processed_ops += 1
                continue
                
            src_str = op.get("src")
            dest_str = op.get("dest")
            if not src_str or not dest_str:
                processed_ops += 1
                continue
                
            src_path = Path(src_str)
            dest_path = Path(dest_str)
            
            # Prevent operations on folders, only files
            if src_path.resolve() == dest_path.resolve():
                processed_ops += 1
                continue
                
            try:
                if copy_mode:
                    if dest_path.exists() and dest_path.is_file():
                        dest_path.unlink()
                        undo_log.append((str(dest_path), "", True, "Deleted copy"))
                    else:
                        undo_log.append((str(dest_path), "", True, "Copy file already deleted or not found"))
                else:
                    if dest_path.exists() and dest_path.is_file():
                        src_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(dest_path, src_path)
                        undo_log.append((str(dest_path), str(src_path), True, "Moved back successfully"))
                    else:
                        undo_log.append((str(dest_path), str(src_path), False, "Organized file not found at destination"))
            except Exception as e:
                undo_log.append((str(dest_path), str(src_path), False, f"Undo error: {e}"))
                
            processed_ops += 1
            if progress_callback:
                progress_callback(processed_ops, total_ops)
                
        return undo_log

    def undo_folder_export(self, history_data: Dict, progress_callback = None) -> List[Tuple[str, str, bool, str]]:
        """
        Undoes a previous folder export operation.
        
        Returns a list of undo operations: (dest_path, src_path, success, message)
        """
        operations = history_data.get("operations", [])
        copy_mode = history_data.get("copy_mode", False)
        
        total_ops = len(operations)
        processed_ops = 0
        undo_log = []
        
        # Count total files in destination folders for move undo progress
        total_files = 0
        if not copy_mode:
            for op in operations:
                dest_str = op.get("dest")
                if dest_str:
                    dest_path = Path(dest_str)
                    if dest_path.exists() and dest_path.is_dir():
                        for root, _, files in os.walk(dest_path):
                            total_files += len(files)
                            
        processed_files = 0
        
        for op in reversed(operations):
            src_str = op.get("src")
            dest_str = op.get("dest")
            if not src_str or not dest_str:
                processed_ops += 1
                if progress_callback:
                    if copy_mode:
                        progress_callback(processed_ops, total_ops)
                    elif total_files > 0:
                        progress_callback(processed_files, total_files)
                continue
                
            src_path = Path(src_str)
            dest_path = Path(dest_str)
            
            try:
                if copy_mode:
                    if dest_path.exists() and dest_path.is_dir():
                        shutil.rmtree(dest_path)
                        undo_log.append((str(dest_path), "", True, "Deleted copied folder"))
                    else:
                        undo_log.append((str(dest_path), "", True, "Copy folder already deleted or not found"))
                    processed_ops += 1
                    if progress_callback:
                        progress_callback(processed_ops, total_ops)
                else:
                    if dest_path.exists() and dest_path.is_dir():
                        # Safety checks on original source path
                        if src_path.exists():
                            if src_path.is_dir() and not any(src_path.iterdir()):
                                src_path.rmdir()
                            else:
                                raise FileExistsError(f"Destination folder already exists and is not empty: {src_path}")
                        
                        src_path.mkdir(parents=True, exist_ok=True)
                        
                        # Copy recursively file-by-file to report progress
                        for root, dirs, files in os.walk(dest_path):
                            relative_dir = Path(root).relative_to(dest_path)
                            dest_sub_dir = src_path / relative_dir
                            dest_sub_dir.mkdir(parents=True, exist_ok=True)
                            
                            for file in files:
                                src_file = Path(root) / file
                                dest_file = dest_sub_dir / file
                                shutil.copy2(src_file, dest_file)
                                processed_files += 1
                                if progress_callback and total_files > 0:
                                    progress_callback(processed_files, total_files)
                                    
                        # Delete the exported folder after copying it back
                        shutil.rmtree(dest_path)
                        undo_log.append((str(dest_path), str(src_path), True, "Moved folder back successfully"))
                    else:
                        undo_log.append((str(dest_path), str(src_path), False, "Exported folder not found at target destination"))
                    
                    # If total_files is 0, we still want to report progress at the end of each folder
                    if progress_callback and total_files == 0:
                        progress_callback(1, 1)
            except Exception as e:
                undo_log.append((str(dest_path), str(src_path), False, f"Undo error: {e}"))
                if progress_callback:
                    if copy_mode:
                        progress_callback(processed_ops, total_ops)
                    elif total_files > 0:
                        progress_callback(processed_files, total_files)
                        
        return undo_log

def calculate_folder_stats(folder_path: Path) -> Tuple[int, int]:
    """Returns (file_count, total_bytes) of the folder."""
    file_count = 0
    total_bytes = 0
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = Path(root) / file
            try:
                total_bytes += file_path.stat().st_size
                file_count += 1
            except Exception:
                pass
    return file_count, total_bytes

def export_folder(
    src_dir: Path, 
    dest_parent: Path, 
    move_mode: bool = False, 
    progress_callback = None
) -> Tuple[bool, str]:
    """
    Copies or moves a folder to a destination parent directory.
    
    progress_callback signature: (current_file_idx, total_files, current_bytes, total_bytes, filename)
    """
    src_path = Path(src_dir).resolve()
    dest_parent_path = Path(dest_parent).resolve()
    
    if not src_path.exists() or not src_path.is_dir():
        return False, "Source folder does not exist"
        
    if not dest_parent_path.exists() or not dest_parent_path.is_dir():
        return False, "Destination folder does not exist"
        
    target_dir = dest_parent_path / src_path.name
    
    if src_path in target_dir.parents or src_path == target_dir:
        return False, "Cannot copy folder inside itself"
        
    file_count, total_bytes = calculate_folder_stats(src_path)
    if file_count == 0:
        return True, "Folder is empty"
        
    processed_files = 0
    processed_bytes = 0
    
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Failed to create target directory: {e}"
        
    try:
        for root, dirs, files in os.walk(src_path):
            relative_dir = Path(root).relative_to(src_path)
            dest_sub_dir = target_dir / relative_dir
            dest_sub_dir.mkdir(parents=True, exist_ok=True)
            
            for file in files:
                src_file = Path(root) / file
                dest_file = dest_sub_dir / file
                
                try:
                    file_size = src_file.stat().st_size
                except Exception:
                    file_size = 0
                    
                shutil.copy2(src_file, dest_file)
                
                processed_files += 1
                processed_bytes += file_size
                
                if progress_callback:
                    progress_callback(processed_files, file_count, processed_bytes, total_bytes, file)
                    
        if move_mode:
            shutil.rmtree(src_path)
            
        return True, "Export completed successfully"
    except Exception as e:
        return False, f"Export error: {e}"
