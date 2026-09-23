// Arduino Morse Code Beacon Controller by W0AIR

const int keyPin = 13;      // Digital pin connected to the interface circuit
const int wpm = 20;         // Speed of the beacon in Words Per Minute (WPM)

// Calculate timing parameters based on WPM configuration
const int dotLen = 1200 / wpm;  // Duration of a single dot in milliseconds
const int dashLen = dotLen * 3; // A dash is 3 times longer than a dot
const int elemGap = dotLen;     // Gap between elements (dots and dashes)
const int letterGap = dotLen * 3;// Gap between letters
const int wordGap = dotLen * 7;  // Gap between words

// Define your Beacon Message here (Keep it UPPERCASE)
const String beaconMessage = "DE K0LTO-1 DN70KH"; 
const long transmitInterval = 250UL; // Delay between transmissions (e.g., 2 seconds)

void setup() {
  pinMode(keyPin, OUTPUT);
  digitalWrite(keyPin, LOW);
  delay (120);
  digitalWrite(keyPin, HIGH);
  delay(300UL); 
  digitalWrite(keyPin, LOW);
}

void loop() {
  // Transmit the Morse code message
  for (int i = 0; i < beaconMessage.length(); i++) {
    char c = beaconMessage.charAt(i);
    if (c == ' ') {
      delay(wordGap - letterGap); // Adjusted because letterGap is added after the previous char
    } else {
      sendMorseChar(c);
      delay(letterGap);
    }
  }

  // --- ADDED: 540 Second Key Down (Carrier Tone) ---
  digitalWrite(keyPin, HIGH);     // Turn the key ON
  delay(540000UL);                 // Hold for 10,000 milliseconds (10 seconds)
  digitalWrite(keyPin, LOW);      // Turn the key OFF
  delay(letterGap);               // Brief gap after the long tone before interval
  
  // Wait for the specified interval before transmitting again
  delay(transmitInterval);
}

void sendMorseChar(char c) {
  // Simple lookup and execution for alphanumeric characters
  switch (c) {
    case 'A': dot(); dash(); break;
    case 'B': dash(); dot(); dot(); dot(); break;
    case 'C': dash(); dot(); dash(); dot(); break;
    case 'D': dash(); dot(); dot(); break;
    case 'E': dot(); break;
    case 'F': dot(); dot(); dash(); dot(); break;
    case 'G': dash(); dash(); dot(); break;
    case 'H': dot(); dot(); dot(); dot(); break;
    case 'I': dot(); dot(); break;
    case 'J': dot(); dash(); dash(); dash(); break;
    case 'K': dash(); dot(); dash(); break;
    case 'L': dot(); dash(); dot(); dot(); break;
    case 'M': dash(); dash(); break;
    case 'N': dash(); dot(); break;
    case 'O': dash(); dash(); dash(); break;
    case 'P': dot(); dash(); dash(); dot(); break;
    case 'Q': dash(); dash(); dot(); dash(); break;
    case 'R': dot(); dash(); dot(); break;
    case 'S': dot(); dot(); dot(); break;
    case 'T': dash(); break;
    case 'U': dot(); dot(); dash(); break;
    case 'V': dot(); dot(); dot(); dash(); break;
    case 'W': dot(); dash(); dash(); break;
    case 'X': dash(); dot(); dot(); dash(); break;
    case 'Y': dash(); dot(); dash(); dash(); break;
    case 'Z': dash(); dash(); dot(); dot(); break;
    case '1': dot(); dash(); dash(); dash(); dash(); break;
    case '2': dot(); dot(); dash(); dash(); dash(); break;
    case '3': dot(); dot(); dot(); dash(); dash(); break;
    case '4': dot(); dot(); dot(); dot(); dash(); break;
    case '5': dot(); dot(); dot(); dot(); dot(); break;
    case '6': dash(); dot(); dot(); dot(); dot(); break;
    case '7': dash(); dash(); dot(); dot(); dot(); break;
    case '8': dash(); dash(); dash(); dot(); dot(); break;
    case '9': dash(); dash(); dash(); dash(); dot(); break;
    case '0': dash(); dash(); dash(); dash(); dash(); break;
    case '-': dash(); dot(); dot(); dot(); dot(); dash(); break;
    case '/': dash(); dot(); dot(); dash(); dot(); break; // Slash separator
  }
}

void dot() {
  digitalWrite(keyPin, HIGH);
  delay(dotLen);
  digitalWrite(keyPin, LOW);
  delay(elemGap);
}

void dash() {
  digitalWrite(keyPin, HIGH);
  delay(dashLen);
  digitalWrite(keyPin, LOW);
  delay(elemGap);
}
