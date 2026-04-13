from gpiozero import Button
from time import sleep

limit_switch = Button(17, pull_up = True)

print("Limit Switch Test")

try:
    while True:
        if limit_switch.is_pressed:
            print("Closed")
        else:
            print("Open")

        sleep(0.1)

except KeyboardInterrupt:
    print("Test Stopped by User")