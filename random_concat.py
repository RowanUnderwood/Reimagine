import os
import random
import string
from collections import Counter
from moviepy.editor import VideoFileClip, CompositeVideoClip, ColorClip, concatenate_videoclips

def get_random_filename(extension=".mp4"):
    """Generates a random filename like 'Result_X7Z2.mp4'."""
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"Result_{suffix}{extension}"

def fit_to_canvas(clip, target_w, target_h):
    """
    Resizes a clip to fit within the target resolution (smart letterboxing/pillarboxing)
    and centers it on a black background.
    """
    # Calculate aspect ratios
    target_ar = target_w / target_h
    clip_ar = clip.w / clip.h

    # Resize logic:
    # If clip is 'wider' than target (e.g. cinematic on 16:9), fit to width
    if clip_ar > target_ar:
        new_clip = clip.resize(width=target_w)
    # If clip is 'taller' than target (e.g. vertical on 16:9), fit to height
    else:
        new_clip = clip.resize(height=target_h)

    # Center the resized clip on a black canvas
    background = ColorClip(size=(target_w, target_h), color=(0, 0, 0), duration=clip.duration)
    final = CompositeVideoClip([background, new_clip.set_position("center")])
    
    return final

def main():
    # 1. Get all mp4 files in current directory
    files = [f for f in os.listdir('.') if f.lower().endswith('.mp4')]
    
    if not files:
        print("No MP4 files found in the current directory.")
        return

    print(f"Found {len(files)} videos. Analyzing aspect ratios and framerates...")

    # 2. Shuffle the order
    random.shuffle(files)

    aspect_ratios = []
    frame_rates = []
    
    # Load clips and gather data
    raw_clips = []
    for f in files:
        try:
            clip = VideoFileClip(f)
            raw_clips.append(clip)
            
            # Round AR to 2 decimals to group similar ratios (e.g. 1.77 vs 1.78)
            ar = round(clip.w / clip.h, 2)
            aspect_ratios.append(ar)
            
            # Collect FPS
            frame_rates.append(clip.fps)
            
        except Exception as e:
            print(f"Skipping corrupt file {f}: {e}")

    if not raw_clips:
        print("No valid clips to process.")
        return

    # 3. Find the most common aspect ratio and framerate
    most_common_ar = Counter(aspect_ratios).most_common(1)[0][0]
    print(f"Most common Aspect Ratio detected: {most_common_ar}")

    # Detect most common FPS (rounded to 3 decimals to group 23.976 etc.)
    # We prioritize the most frequent FPS to avoid upscaling bulk 30fps content to 60fps 
    # just because of one outlier, or vice versa.
    rounded_fps = [round(f, 3) for f in frame_rates]
    most_common_fps = Counter(rounded_fps).most_common(1)[0][0]
    print(f"Most common FPS detected: {most_common_fps}")

    # 4. Determine Target Resolution
    # We look for the maximum resolution among videos that match the most common AR.
    target_w, target_h = 0, 0
    for clip in raw_clips:
        ar = round(clip.w / clip.h, 2)
        if ar == most_common_ar:
            if clip.w > target_w:
                target_w = clip.w
                target_h = clip.h
    
    print(f"Target Resolution set to: {target_w}x{target_h}")

    # 5. Process clips (Resize/Letterbox)
    processed_clips = []
    print("Processing clips (Resizing and Letterboxing)...")
    
    for clip in raw_clips:
        # If the clip already matches dimensions exactly, append it directly
        if clip.w == target_w and clip.h == target_h:
            processed_clips.append(clip)
        else:
            # Apply smart letterboxing
            processed = fit_to_canvas(clip, target_w, target_h)
            processed_clips.append(processed)

    # 6. Concatenate
    print("Concatenating video... (This may take some time)")
    # method='compose' is necessary when clips have been resized/composited
    final_video = concatenate_videoclips(processed_clips, method="compose")

    # 7. Write Output
    output_filename = get_random_filename()
    print(f"Writing to {output_filename} at {most_common_fps} FPS...")
    
    # Updated to use the detected most_common_fps instead of hardcoded 30
    final_video.write_videofile(output_filename, codec="libx264", fps=most_common_fps, preset="ultrafast")

    # Cleanup
    for clip in raw_clips:
        clip.close()
    
    print("Done!")

if __name__ == "__main__":
    main()