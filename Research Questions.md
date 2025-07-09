# Meteor Scatter QSO Party Research Questions and Objectives

**Objective:** Generate research-worthy data resulting from HF and VHF meter meteor scatter operation. The data will be used by the research community to answer science questions such as:

## Primary Research Questions
*These are questions that we plan to have closure on.*
1. What factors influence the strength of HF meteor scatter propagations? e.g., meteor shower radiant location, radio frequency, meteoroid size or velocity?
2. What is the typical duration of useful HF and VHF meteor scatter propagations? How does the meteor scatter duration changes with wavelenght, Tx-Rx distance, meteor velocity?
3. What is the minimum size of amateur radio station needed to work meteor scatter operations?
4. Compare astronomical observations with amateur radio observations
5. How do we distinguish meteor scatter communications from other propagation modes?
   1. What percentage of reported meteor scatter QSOs are actually meteor scatter?
   2. What percentage are the other modes?
  
## Secondary Research Questions
*These are questions we are interested in, but may not be the prime focus of the MSQP, or we may not have a clear path to closure with our available methodology.*

The target communities include: Seasoned meteor scatter operators, meteor scatter 'rookies' (those who are new to the mode), researchers with an interest in radio wave propagation.  

-----
Since our brief discussion at the HamSCI call a couple of weeks ago I’ve been giving some thought to possible science objectives for the meteor scatter work. I’d be interested to hear how these ideas fit with your vision for the events. 

  

I figure the most interesting thing we can do now that hasn’t been done before is to compare 6m and 10m propagation. As you know, we’ve only been allowed to use MSK144 on 10m for a few months and I didn’t see a lot of activity on Ping Jockeys (or on the air) on 10m during the Lyrids. If we can show the advantages over 6m, which are theoretically there, we might increase future activity. 

  

The theory says that the scattering process favors 10m (see bullets below) but there is another process called “initial trail radius effect” which says that ionization trails of certain sizes can cause destructive interference of the signal. That trail radius is larger when the meteor ablates at higher altitudes which happens for faster meteors. Relative results from Perseids and Geminids, and other showers as well, should be interesting. Perseids have a geocentric velocity of 60 km/s and Geminids are 36 km/s which changes their average ablation heights and initial trail radii significantly. 

  

The Holy Grail of most meteor research is to measure the flux of meteoroids above a certain size limit and to determine the population index (or mass index) which is the size distribution. Given the complex dependence on scattering geometry (which I can discuss) and transmit and receive powers and sensitivities I’m not proposing to tackle that problem. Our colleagues at the University of Western Ontario have a well-calibrated multi-frequency backscatter radar with outlier time-of-flight receiver stations and have been working that problem for about 3 decades so I think the citizen science aspect of this event lends itself better to the topics I outlined above. 

  

Below is a rough outline for a talk I could give at a future meeting. I’d like to see if you are interested or have any suggestions on this before I put it together. I’ll pull some material from my past talks on the subject so it shouldn’t take too long to develop. 

  

Let me know your thoughts. I’ll try to make a future Thursday afternoon call. 

  

Rob 

  

  

HamSCI meteor scatter thoughts 

Rob Suggs NN4NT 

NASA MSFC Amateur Radio Club 

  
Science/engineering goal - compare performance of 6m and 10m bands for meteor scatter 

The recent lifting of the 300 baud limit below 50 MHz allows MSK144 to be used for 10m 

Theory says 10m should be better as signal strength goes as the cube of wavelength 

Theory says 10m should be better as signal duration goes as the square of the wavelength 

Show equations on this from McKinley 

Initial trail radius also affects the scattered signal. It is a function of meteor speed 

  
Network of transmit and receive stations can provide the data - enable PSKReporter reporting 

Decoding grid squares provides good location data. 

Encourage use of frequencies besides the calling freq to avoid local interference issues. 

  
Talk about specular geometry, underdense and overdense meteors 

Difficult to get flux as a function of size due to the geometry and speed dependence 

UWO has worked this out with backscatter radar and time-of-flight stations 


Risks/data contamination 

Other propagation modes can cause signals to be “counted” when not meteors 

Tropo, F layer, E layer, auroral 

Best discriminator is length of signal - can WSJT-X provide this real-time or post-processing? WAV files are useful but analysis is potentially labor-intensive. 

~ 1 second signals are likely underdense meteors. Filter for those.  

There can be overdense meteors that would be rejected by this filter but they don’t have to satisfy the specular condition either. But maybe we don’t care... 


Show slides giving background of meteor showers an parent bodies (mostly cometary) and sporadic source locations, their comet family sources and speeds. Basic meteor science. 


Related investigations 

N4WLO beacons running on 6m and 10m now. Located near Mobile AL. I’ll reach out and see if he would like to participate, if he isn’t already plugged in. I regularly hear meteors on 10m on his beacon frequency. 

TV station ping counts - easy for anyone with an SDR. My count software selects the underdense. I started doing this 25 years ago in the analog TV signal era and have a receiver which has been running for the last year using my count software. It still works using the digital TV pilot tone. This is easy to do with a dipole and SDR and lends itself to continuous monitoring. It also sounds cool as the signals are true pings.  

  

Possible future talks 
