# -*- coding: utf-8 -*-
"""
Created on Tue Oct 28 19:51:53 2025
by Microsoft CoPilot
modified by Rob Suggs NN4NT

"""

import os
import numpy as np
import matplotlib.pyplot as plt
import scipy.io.wavfile as wav
from tinytag import TinyTag

# Directory containing WAV files - get the slashes oriented the right way
#directory = 'C:/Users/robsu/Desktop/HamSCI 2025 MSQP/MSQP 2025 Perseids/NN4SA 10m/NN4SA_EM64pp_10m_4el_TH11_NE'  
# Replace with your actual path. Make sure slashes are forward.

# add tinytag to read metadata
# =============================================================================
# from tinytag import TinyTag
# 

directory= os.getcwd() # use current working directory, navigate with the little folder

print(directory)

# Parameters
window_duration = 0.072  # 72 milliseconds is the length of the MSK144 message
freq_min = 500 # start frequency in Hz
freq_max = 2800 # end frequency in Hz

# Process each WAV file in the directory
for filename in os.listdir(directory):
    if filename.lower().endswith('.wav'):
        filepath = os.path.join(directory, filename)
        print(f'Processing {filename}...')
# Load the audio file to read the tag
        tag = TinyTag.get(filepath)
# 
# Extract properties
#        print(f"Title: {tag.title}")
# print(f"Artist: {tag.artist}")
# print(f"Album: {tag.album}")
# print(f"Duration: {tag.duration:.2f} seconds")
# print(f"Bitrate: {tag.bitrate} kbps")
# print(f"Year: {tag.year}")
        comment = {tag.comment}
        print("Comment:", comment) # and as a label on the plots
# =============================================================================

        # Load WAV file
        sample_rate, data = wav.read(filepath)

        # If stereo, take one channel
        if len(data.shape) > 1:
            data = data[:, 0]

        window_size = int(sample_rate * window_duration)
        num_windows = len(data) // window_size

        times = []
        avg_amplitudes = []

        for i in range(num_windows):
            start = i * window_size
            end = start + window_size
            segment = data[start:end]

            # Apply FFT
            fft_result = np.fft.rfft(segment)
            freqs = np.fft.rfftfreq(len(segment), d=1/sample_rate)
            amplitudes = np.abs(fft_result)

            # Filter and average amplitude in desired frequency range
            mask = (freqs >= freq_min) & (freqs <= freq_max)
            avg_amplitude = np.mean(amplitudes[mask])

            times.append(i * window_duration)
            avg_amplitudes.append(avg_amplitude)

        # Plot
        plt.figure(figsize=(10, 4))
        plt.plot(times, avg_amplitudes, label='Avg amplitude (500–2800 Hz)')
        plt.xlabel('Time (s)')
        plt.ylabel('Amplitude')
        plt.title(f'{filename} {tag.comment} - Signal Amplitude ' )
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(directory, f'{filename}_amplitude_plot.png'))
        plt.show()
        plt.close()
