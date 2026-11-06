"""Fixed settings: TV channels, audio rate, spectrum and detection parameters."""

# DTV pilot carriers (MHz): 309.441 kHz above each channel's lower edge (ATSC
# A/53). The receiver is tuned 1 kHz below the pilot in upper sideband, so each
# pilot lands near 1000 Hz in the audio. Stations offset from the nominal pilot
# by tens of Hz appear correspondingly off 1000 Hz.
PILOT_MHZ = {ch: edge + 0.309441 for ch, edge in {2: 54, 3: 60, 4: 66, 5: 76, 6: 82}.items()}
AUDIO_OFFSET_HZ = 1000.0

AUDIO_RATE = 8000   # all processing runs on 8 kHz audio, from SDR or sound card

# Spectrum used to find echoes: 1024-point FFTs every 16 ms give 7.8 Hz bins
# with a 128 ms window. Only 500-1500 Hz is searched.
FFT_SIZE = 1024
HOP = 128
F_LO, F_HI = 500.0, 1500.0

# Detection, in dB relative to each bin's own noise floor. A bin with a steady
# direct-path carrier has a high floor, so only rises above the carrier count.
THRESHOLD_DB = 10.0   # an echo's peak must reach this (adjustable in the GUI)
EDGE_DB = 6.0         # an echo starts and ends where the bin crosses this.
                      # A single bin of noise swings widely: 4 dB catches 13% of bins at any moment.
SMOOTH_FRAMES = 3     # spectra averaged before comparing with the floor
FLOOR_WINDOW_S = 60.0 # each bin's floor is its median power over this long
FLOOR_UPDATE_S = 1.0
WARMUP_S = 15.0       # no detections until the floors have settled
MERGE_GAP_S = 0.10    # dips shorter than this do not end an echo
GROUP_BINS = 3        # echoes this many bins apart at the same time are one meteor
GROUP_HOLD_S = 0.3    # wait this long after an echo ends for neighbours to finish
BROADBAND_FRACTION = 0.2  # more bins than this above the threshold at once is impulse noise

# Decay fit, on a narrow-band envelope around the detected frequency. It has
# much finer time resolution than the FFT, which matters at channels 5-6 where
# underdense decay times fall below 100 ms.
ENV_BW_HZ = 25.0      # envelope filter half-width, when no other carrier is near
MIN_ENV_BW_HZ = 6.0   # narrowest filter used to keep out a nearby carrier
OWN_CARRIER_HZ = 4.0  # a carrier this close is the echo's own transmitter
ENV_STEP_S = 0.004    # envelope sample spacing
NOISE_BEFORE_S = (1.5, 0.3)  # noise is measured from 1.5 s to 0.3 s before onset
MAX_DURATION_S = 2.0  # underdense: shorter than this above EDGE_DB
MAX_RISE_S = 0.20     # sharp rise: onset to peak within this
FIT_TAIL_S = 0.30     # noise-floor time included after the echo in the fit
MIN_R2 = 0.3          # minimum goodness of fit, in dB, over the echo and 0.3 s after
MIN_INTEGRATED_SNR_S = 0.8  # echo energy / noise power, summed over the echo (s)
# Both were first set on synthetic data. MIN_R2 was lowered from 0.4 to 0.3
# after 8 h of MSFC channel 3 audio (Aug 2026): echoes with R2 0.3-0.4 sounded
# and looked like meteors (rippled decays, head-echo Doppler, very short
# echoes), and none fell off the station frequencies, where noise would land.
TAU_RANGE_S = (0.005, 3.0)
MAX_PLATEAU_S = 0.15  # longest level stretch before the decay

AUDIO_RING_S = 20.0   # audio kept for the decay fit
CLIP_BEFORE_S, CLIP_AFTER_S = 2.0, 2.5  # audio saved around each logged echo's peak
