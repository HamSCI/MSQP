# Meteor Scatter QSO Party Research Questions and Objectives

**Objective:** Generate research-worthy data resulting from HF and VHF meter meteor scatter operations. The data will be used by the research community to answer science questions such as:

## Primary Research Questions
*These are questions that we plan to have closure on.*
1. What factors influence meteor scatter propagation?
   - What are the similarities and differences between HF and VHF meteor scatter propagation?
   - How does propagation change between two meteor showers?
   - How does propagation change with radiant location, trail direction, meteoroid size, and velocity?
2. What is the typical duration of useful meteor scatter propagation?
   - How does this duration vary with radio frequency, transmitter–receiver distance, and meteor velocity?
4. What is the minimum size of an amateur radio station needed to work meteor scatter operations?
   - How does this minimum station size vary between HF and VHF bands?
6. How can meteor scatter communication be distinguished from other propagation modes?
   - What percentage of reported meteor scatter QSOs are actually meteor scatter?
   - What percentage are due to other modes (e.g., tropospheric, F-layer, E-layer, auroral)?
7. How do astronomical meteor observations compare with amateur radio observations?

## Secondary Research Questions
*These are questions we are interested in, but may not be the prime focus of the MSQP, or we may not have a clear path to closure with our available methodology.*

The target communities include: Seasoned meteor scatter operators, meteor scatter 'rookies' (those who are new to the mode), researchers with an interest in radio wave propagation.  

-----
Expressions for the power seen by the receiver $P_R$ (Watts) and echo duration are as follows,

$$ P_R \space \propto \space \frac{\lambda^3}{(R_1 R_2)(R_1 + R_2)(1 - \sin^2 \phi \space \cos^2 \beta)} $$  

$$ T \space \propto \space \lambda^2 \sec^2 \phi $$  

**Where:** 
$\lambda$ = radio wave wavelength,  
$R_1$ = distance between meteor trail and transmitter,  
$R_2$ = distance between meteor trail and receiver,  
$\phi$ = half of the angle between the r1 and r2 lines,  
$\beta$ = angle between meteor trail and the intersection line of the tangent plane and plane of propagation 

The equations show that the farther apart the transmitter and receiver are, the more power the meteor trail reflects, and the longer the echo lasts. However, at some point, the signal loss from the large distance (the terms involving $R_1$ and $R_2$) becomes too strong and cancels out the benefit of increasing the distance and angle $\phi$. Still, for a while (depending on the transmitter power), this setup has advantage over the backscatter. Therefore, placing the transmitter and receiver several hundred kilometers apart allows us to detect fainter and higher meteors than if both were in the same location.

Reference:  
McKinley, Donald William Robert. "Meteor science and engineering." New York (1961).  
Some Notes and Equations for Forward Scatter compiled by James Richardson https://amsmeteors.org/radio/scatter_notes.txt

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
