import librosa
import numpy as np
import matplotlib.pyplot as plt
import librosa.display
import os

def convert_mp3_to_spectrogram(file_path):
    # Load the MP3 file
    y, sr = librosa.load(file_path, sr=None)

    # Normalize the waveform data
    y_normalized = y / np.max(np.abs(y))

    # Convert to spectrogram
    S = librosa.feature.melspectrogram(y=y_normalized, sr=sr)
    S_dB = librosa.power_to_db(S, ref=np.max)

    # Generate output image path
    base, _ = os.path.splitext(file_path)
    output_image_path = f"{base}.png"

    # Calculate the duration of the audio in seconds
    duration = librosa.get_duration(y=y, sr=sr)

    # Save the spectrogram as an image with time reference
    plt.figure(figsize=(10, 4))
    librosa.display.specshow(S_dB, sr=sr, x_axis='time', y_axis='mel')
    plt.colorbar(format='%+2.0f dB')
    plt.title('Mel-frequency spectrogram')
    plt.xlabel('Time (s)')
    plt.ylabel('Frequency (Hz)')
    plt.xlim(0, duration)  # Set x-axis limits to the duration of the audio
    plt.tight_layout()
    plt.savefig(output_image_path)
    plt.close()

    return output_image_path

if __name__ == "__main__":
    import argparse

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Convert MP3 to Spectrogram")
    parser.add_argument("file_path", type=str, help="Path to the MP3 file")

    # Parse arguments
    args = parser.parse_args()

    # Convert MP3 to spectrogram
    output_image_path = convert_mp3_to_spectrogram(args.file_path)
    print(f"Spectrogram saved to {output_image_path}")

