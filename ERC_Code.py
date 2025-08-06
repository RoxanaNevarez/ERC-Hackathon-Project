# ------ Exercise Repetition Counter ------
# Function: counts repetitions of any exercise measured by proximity between a person and a distance sensor
#           Uses a 3461BS LED display to show the number of repetitions and the threshold
#           Uses a potentiometer to set the threshold distance depending on the exercise
#           Uses a buzzer to signal each repetition
#           Uses a reset button to reset the counter

# --- Importing Necessary CircuitPython Libraries ---
import time # library for time management
import board # library for Metro M0 board pin definitions
import digitalio # library for push button and 3461BS LED display
import adafruit_hcsr04 # library for HC-SR04 ultrasonic sensor
import analogio # library for potentiometer
import pwmio # library for buzzer

# --- Common Anode Display Setup ---
# 3461BS LED display has 4 digits and 7 segments per digit
digit_pins = [board.D4, board.A2, board.D6, board.D7]
segment_pins = [board.D8, board.D9, board.D10, board.D11, board.D12, board.D13, board.A0]

# --- Initializing Lists for Digits and Segments ---
digits = []
segments = []

# --- Distance Sensor Setup ---
sonar = adafruit_hcsr04.HCSR04(trigger_pin=board.D2, echo_pin=board.D3)

# --- Reset Button Setup ---
reset_pin = digitalio.DigitalInOut(board.A5) # pin connection
reset_pin.direction = digitalio.Direction.INPUT # button input
reset_pin.pull = digitalio.Pull.UP # button behaves as pull-up resistor (HIGH when not pressed ~ pin reads VCC)
last_reset_state = True # last state of reset button

# --- Potentiometer Setup ---
potentiometer = analogio.AnalogIn(board.A1) # pin connection
last_pot_value = -1 # last value of potentiometer
pot_tolerance = 1000 # adjusts sensitivity (smaller value = more sensitive = more flickering of LED display)

# --- Avoiding Double Counting ---
object_inside = False # tracks if an object is inside the threshold zone (adjusted by potentiometer)

# --- Buzzer Setup ---
buzzer = pwmio.PWMOut(board.D5, duty_cycle=0, frequency=440, variable_frequency=True)

# --- For Loops to Initialize Digits and Segments of LED Display ---
for pin in digit_pins:
    p = digitalio.DigitalInOut(pin)
    p.direction = digitalio.Direction.OUTPUT # display output (shows digit pins on the display)
    p.value = False # LOW = 0 = ON (common anode)
    digits.append(p) # modifies list of digits in place rather than creating a new list

for pin in segment_pins:
    p = digitalio.DigitalInOut(pin)
    p.direction = digitalio.Direction.OUTPUT # display output (shows segment pins on the display)
    p.value = True # HIGH = 1 = OFF (common anode)
    segments.append(p) # modifies list of segments in place rather than creating a new list

# --- Segment Patterns for Common Anode LED Display: 0 = ON, 1 = OFF ---
digit_patterns = {
    #   a  b  c  d  e  f  g 
    0: [0, 0, 0, 0, 0, 0, 1],
    1: [1, 0, 0, 1, 1, 1, 1],
    2: [0, 0, 1, 0, 0, 1, 0],
    3: [0, 0, 0, 0, 1, 1, 0],
    4: [1, 0, 0, 1, 1, 0, 0],
    5: [0, 1, 0, 0, 1, 0, 0],
    6: [0, 1, 0, 0, 0, 0, 0],
    7: [0, 0, 0, 1, 1, 1, 1],
    8: [0, 0, 0, 0, 0, 0, 0],
    9: [0, 0, 0, 0, 1, 0, 0]
}

# --- Display Variables (Initial States) ---
counter = 0 # repetition counter starts at 0
display_digits = [0, 0, 0, 0] # seen on the display as [TD CV] = [Threshold Distance (inches), Counter Value]
current_digit = 0 # initial digit displayed
beep_active = False # buzzer state
beep_start_time = 0 # time when buzzer is activated
beep_duration = 0.3 # buzzing duration (seconds)

# --- Timing Control ---
last_display_time = 0
DISPLAY_INTERVAL = 0.002 # ~2ms per digit = ~125Hz refresh rate (fast enough for smooth display - minimal flickering)

# --- Sensor Control ---
last_sensor_time = 0
SENSOR_INTERVAL = 0.1 # 10Hz sensor polling (quickly detects changes in sensor's readings)
ready_for_next = True # detection logic

# ------ Function Definitions ------

# --- update display digits from counter integer value ---
def update_display_digits(val):
    val = val % 10000
    # splitting the value into thousands, hundreds, tens, and ones
    t = val // 1000
    h = (val % 1000) // 100
    te = (val % 100) // 10
    o = val % 10

    if val < 10:
        return [-1, -1, -1, o] # only ones place is shown
    elif val < 100:
        return [-1, -1, te, o] # only tens and ones places are shown
    elif val < 1000:
        return [-1, h, te, o] # only hundreds, tens, and ones places are shown
    else:
        return [t, h, te, o] # all places are shown

# --- refresh the display by cycling through digits ---
def refresh_display():
    global current_digit
    # turning off all digits from display
    for d in digits:
        d.value = False # common anode: LOW = ON

    # turning off all segments from display
    for s in segments:
        s.value = True # common anode: HIGH = OFF

    val = display_digits[current_digit]
    if val != -1:
        pattern = digit_patterns[val] # get the segment pattern for the current digit
        for i in range(7):
            segments[i].value = pattern[i] # set the segments according to the pattern
        digits[current_digit].value = True # common anode: HIGH = OFF

    current_digit = (current_digit + 1) % 4 # cycle through the four digits

# --- get potentiometer value and calculate threshold distance ---
def get_pot_value():
    raw = potentiometer.value  # 0 to 65535 (binary number range)
    threshold_cm = 5.0 + (raw / 65535) * (92.0 - 5.0)
    threshold_in = threshold_cm / 2.5 # 2.54cm rounded to 2.5cm for display to stop flickering between 01 and 02
    return raw, threshold_in

# --- combine threshold distance and counter value into a list of four digits ---
def combine_threshold_and_counter(threshold, counter):
    # Return four digits: TD CV [Threshold Distance (in), Counter Value]
    t = int(threshold) # convert threshold distance to integer
    c = int(counter) # convert counter value to integer

    t = max(0, min(t, 99)) # limit threshold distance to 0-99 inches
    c = max(0, min(c, 99)) # limit counter value to 0-99

    t_tens = t // 10 # tens place of threshold distance
    t_ones = t % 10 # ones place of threshold distance
    c_tens = c // 10 # tens place of counter value
    c_ones = c % 10 # ones place of counter value

    return [t_tens, t_ones, c_tens, c_ones] # returns a list of four digits to be displayed

# --- start beep function at given frequency---
def start_beep(frequency=4000): 
    global beep_active, beep_start_time
    buzzer.frequency = frequency
    buzzer.duty_cycle = 32768  # 50% duty cycle
    beep_start_time = time.monotonic()
    beep_active = True


# Initial Display State on Serial Monitor
raw, threshold = get_pot_value()
display_digits = combine_threshold_and_counter(threshold, counter)
print("Starting Counter")

while True:
    now = time.monotonic()
    # Non-blocking Buzzer Beep
    if beep_active:
        if time.monotonic() - beep_start_time >= beep_duration:
            buzzer.duty_cycle = 0  # turn off beep
            beep_active = False

    # Refresh Display
    if now - last_display_time >= DISPLAY_INTERVAL:
        refresh_display()
        last_display_time = now

    # Reset Button
    reset_state = reset_pin.value
    if not reset_state and last_reset_state:
        counter = 0
        print("Counter Reset") # display reset message on serial monitor
    last_reset_state = reset_state

    # Sensor Read
    if now - last_sensor_time >= SENSOR_INTERVAL:
        try:
            distance = sonar.distance
            raw, threshold = get_pot_value()

            if abs(raw - last_pot_value) > pot_tolerance:
                print(f"Threshold: {threshold:.1f} in") # display threshold distance on serial monitor
                last_pot_value = raw

            threshold_cm = threshold * 2.54
            detected = distance <= threshold_cm

            if detected and not object_inside: # object just entered threshold zone
                counter += 1
                print(f"Rep #{counter} detected") # display current repetition detected
                start_beep() # short beep
                object_inside = True  # set state to "inside"
            
            elif not detected and object_inside: # object has left threshold zone
                object_inside = False  # reset state

            # Update Display
            display_digits = combine_threshold_and_counter(threshold, counter)

        except RuntimeError:
            pass  # ignore invalid reads

        last_sensor_time = now

