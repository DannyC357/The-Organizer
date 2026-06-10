import os
import shutil
import json
from pathlib import Path
from organizer_engine import AudioClassifier, OrganizerEngine, calculate_folder_stats, export_folder

def create_mock_environment(test_dir: Path):
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    
    kit_a = test_dir / "Classic 808 Kit"
    kit_b = test_dir / "Acoustic Snare Kit"
    
    kit_a.mkdir(parents=True, exist_ok=True)
    kit_b.mkdir(parents=True, exist_ok=True)
    
    mock_files = [
        # Kit A (Classic 808 Kit)
        (kit_a / "808_kick_sub.wav", "Kicks"),
        (kit_a / "snr_vintage.wav", "Snares"),
        (kit_a / "closed_hihat_909.wav", "Hi-Hats"),
        (kit_a / "clap_analog.wav", "Claps"),
        (kit_a / "perc_shaker_01.wav", "Percussion"),
        (kit_a / "vocal_vox_hey.wav", "Vocals & Vox"),
        (kit_a / "weird_unrelated_file.wav", "Uncategorized"),
        
        # Kit B (Acoustic Snare Kit)
        (kit_b / "snare_acoustic_05.wav", "Snares"),
        (kit_b / "kick_acoustic_deep.wav", "Kicks"),
        (kit_b / "open_hat_raw.wav", "Hi-Hats"),
        (kit_b / "crash_cymb.wav", "Cymbals"),
        (kit_b / "tom_high.wav", "Toms"),
        (kit_b / "fx_riser_120bpm.wav", "FX & Textures"),
    ]
    
    for file_path, expected_cat in mock_files:
        with open(file_path, "w") as f:
            f.write("mock audio content")
            
    return mock_files, kit_a, kit_b

def test_inplace_with_undo(test_dir: Path, engine: OrganizerEngine):
    print("\n=============================================")
    print("TEST 1: In-Place Mode (subfolders) + UNDO")
    print("=============================================")
    
    mock_files, kit_a, kit_b = create_mock_environment(test_dir)
    scan_results = engine.scan_directory(test_dir, recursive=True)
    
    print("Executing In-Place organization...")
    ops = engine.organize(test_dir, scan_results, copy_mode=False, consolidate_mode=False)
    
    # Verify locations after organize
    for src, dest, success, msg in ops:
        assert success, f"Organize operation failed: {msg}"
    
    # Verify files moved to categories
    assert (kit_a / "Kicks" / "808_kick_sub.wav").exists()
    assert (kit_b / "Snares" / "snare_acoustic_05.wav").exists()
    
    # Build history structure for undo
    history_ops = []
    for src, dest, success, msg in ops:
        if success and dest and src != dest and "Already in place" not in msg:
            history_ops.append({"src": src, "dest": dest, "success": success})
            
    history_data = {
        "type": "file_organization",
        "copy_mode": False,
        "operations": history_ops
    }
    
    print("Executing Undo on In-Place organization...")
    undo_ops = engine.undo_organization(history_data)
    for dest, src, success, msg in undo_ops:
        assert success, f"Undo operation failed: {msg}"
        
    # Verify locations are restored
    for file_path, expected_cat in mock_files:
        assert file_path.exists(), f"File was not restored by undo: {file_path.name}"
        
    # Verify category folders are cleaned up
    assert not (kit_a / "Kicks" / "808_kick_sub.wav").exists()
    assert not (kit_b / "Snares" / "snare_acoustic_05.wav").exists()
    
    print("PASS: In-Place organization and Undo completed successfully!")

def test_consolidate_with_undo(test_dir: Path, engine: OrganizerEngine):
    print("\n=============================================")
    print("TEST 2: Consolidate Mode (main folder) + UNDO")
    print("=============================================")
    
    mock_files, kit_a, kit_b = create_mock_environment(test_dir)
    scan_results = engine.scan_directory(test_dir, recursive=True)
    
    print("Executing Consolidate organization...")
    ops = engine.organize(test_dir, scan_results, copy_mode=False, consolidate_mode=True)
    
    # Verify locations after organize
    for src, dest, success, msg in ops:
        assert success, f"Organize operation failed: {msg}"
        
    # Verify files consolidated at root
    assert (test_dir / "Kicks" / "Classic 808 Kit - 808_kick_sub.wav").exists()
    assert (test_dir / "Snares" / "Acoustic Snare Kit - snare_acoustic_05.wav").exists()
    
    # Build history structure for undo
    history_ops = []
    for src, dest, success, msg in ops:
        if success and dest and src != dest and "Already in place" not in msg:
            history_ops.append({"src": src, "dest": dest, "success": success})
            
    history_data = {
        "type": "file_organization",
        "copy_mode": False,
        "operations": history_ops
    }
    
    print("Executing Undo on Consolidate organization...")
    undo_ops = engine.undo_organization(history_data)
    for dest, src, success, msg in undo_ops:
        assert success, f"Undo operation failed: {msg}"
        
    # Verify locations are restored
    for file_path, expected_cat in mock_files:
        assert file_path.exists(), f"File was not restored by undo: {file_path.name}"
        
    # Verify consolidated files are deleted from root
    assert not (test_dir / "Kicks" / "Classic 808 Kit - 808_kick_sub.wav").exists()
    assert not (test_dir / "Snares" / "Acoustic Snare Kit - snare_acoustic_05.wav").exists()
    
    print("PASS: Consolidate organization and Undo completed successfully!")

def test_copy_mode_undo(test_dir: Path, engine: OrganizerEngine):
    print("\n=============================================")
    print("TEST 3: Copy Mode + UNDO (Delete Copies)")
    print("=============================================")
    
    mock_files, kit_a, kit_b = create_mock_environment(test_dir)
    scan_results = engine.scan_directory(test_dir, recursive=True)
    
    print("Executing organization in COPY mode...")
    ops = engine.organize(test_dir, scan_results, copy_mode=True, consolidate_mode=True)
    
    # Verify both source and copy exist
    assert (kit_a / "808_kick_sub.wav").exists()
    assert (test_dir / "Kicks" / "Classic 808 Kit - 808_kick_sub.wav").exists()
    
    # Build history
    history_ops = []
    for src, dest, success, msg in ops:
        if success and dest and src != dest and "Already in place" not in msg:
            history_ops.append({"src": src, "dest": dest, "success": success})
            
    history_data = {
        "type": "file_organization",
        "copy_mode": True,
        "operations": history_ops
    }
    
    print("Executing Undo on Copy organization...")
    undo_ops = engine.undo_organization(history_data)
    for dest, src, success, msg in undo_ops:
        assert success, f"Undo operation failed: {msg}"
        
    # Verify original files still exist
    for file_path, expected_cat in mock_files:
        assert file_path.exists(), f"Original file was deleted by copy undo: {file_path.name}"
        
    # Verify copy files are deleted
    assert not (test_dir / "Kicks" / "Classic 808 Kit - 808_kick_sub.wav").exists()
    
    print("PASS: Copy mode organization and Undo completed successfully!")

def test_folder_export_with_undo(test_dir: Path, engine: OrganizerEngine):
    print("\n=============================================")
    print("TEST 4: Folder Export + UNDO (Copy vs Move)")
    print("=============================================")
    
    # Create mock environment
    mock_files, kit_a, kit_b = create_mock_environment(test_dir)
    
    # Destination directory
    export_dest = test_dir / "ExportedKits"
    export_dest.mkdir(parents=True, exist_ok=True)
    
    # Verify calculate_folder_stats
    file_count, size_bytes = calculate_folder_stats(kit_a)
    assert file_count == 7, f"Expected 7 files in kit_a, got {file_count}"
    assert size_bytes > 0, "Expected folder size to be greater than 0 bytes"
    
    # 1. Test Copy Export + Undo
    print("Running copy export of Kit A...")
    success, msg = export_folder(kit_a, export_dest, move_mode=False)
    assert success, f"Copy export failed: {msg}"
    
    # Verify files exist in both
    assert (kit_a / "808_kick_sub.wav").exists()
    assert (export_dest / "Classic 808 Kit" / "808_kick_sub.wav").exists()
    
    # Undo Copy Export
    history_data_copy = {
        "type": "folder_export",
        "copy_mode": True,
        "operations": [{"src": str(kit_a), "dest": str(export_dest / kit_a.name)}]
    }
    print("Undoing Copy Export...")
    undo_ops = engine.undo_folder_export(history_data_copy)
    for dest, src, success, msg in undo_ops:
        assert success, f"Undo copy export failed: {msg}"
        
    # Verify copy folder deleted, source folder remains
    assert not (export_dest / "Classic 808 Kit").exists()
    assert (kit_a / "808_kick_sub.wav").exists()
    print("Copy export undo verified.")
    
    # 2. Test Move Export + Undo with progress tracking and safety checks
    print("Running move export of Kit B...")
    success, msg = export_folder(kit_b, export_dest, move_mode=True)
    assert success, f"Move export failed: {msg}"
    
    # Verify moved
    assert not kit_b.exists()
    assert (export_dest / "Acoustic Snare Kit" / "snare_acoustic_05.wav").exists()
    
    # Trace progress callbacks
    progress_calls = []
    def progress_cb(current, total):
        progress_calls.append((current, total))
        
    # Test Safety Check: Recreate source directory as non-empty
    kit_b.mkdir(parents=True, exist_ok=True)
    conflict_file = kit_b / "conflict.wav"
    with open(conflict_file, "w") as f:
        f.write("conflicting file")
        
    history_data_move = {
        "type": "folder_export",
        "copy_mode": False,
        "operations": [{"src": str(kit_b), "dest": str(export_dest / kit_b.name)}]
    }
    
    print("Undoing Move Export (should fail due to safety check)...")
    undo_ops = engine.undo_folder_export(history_data_move, progress_callback=progress_cb)
    assert len(undo_ops) == 1
    assert not undo_ops[0][2], "Expected undo to fail because target folder exists and is not empty"
    assert "Destination folder already exists and is not empty" in undo_ops[0][3]
    
    # Clean up conflicting folder
    shutil.rmtree(kit_b)
    
    print("Undoing Move Export (should succeed now)...")
    progress_calls.clear()
    undo_ops = engine.undo_folder_export(history_data_move, progress_callback=progress_cb)
    for dest, src, success, msg in undo_ops:
        assert success, f"Undo move export failed: {msg}"
        
    # Verify restored at original path, deleted at dest
    assert not (export_dest / "Acoustic Snare Kit").exists()
    assert kit_b.exists()
    assert (kit_b / "snare_acoustic_05.wav").exists()
    
    # Verify progress callback was triggered for all 6 files in Kit B
    assert len(progress_calls) == 6, f"Expected 6 progress calls, got {len(progress_calls)}"
    assert progress_calls[-1] == (6, 6), f"Expected final progress to be (6, 6), got {progress_calls[-1]}"
    print("Move export undo verified with safety checks and granular progress.")
    
    print("PASS: Folder export operations and Undo completed successfully!")

def run_tests():
    test_dir = Path(__file__).parent / "temp_test_kit"
    classifier = AudioClassifier()
    engine = OrganizerEngine(classifier)
    
    try:
        test_inplace_with_undo(test_dir, engine)
        test_consolidate_with_undo(test_dir, engine)
        test_copy_mode_undo(test_dir, engine)
        test_folder_export_with_undo(test_dir, engine)
        
        print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print("Temporary test environment cleaned up.")

if __name__ == "__main__":
    run_tests()
