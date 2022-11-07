import pyaudio
import wave
import uuid
import requests
import os
import audioop
import csv
import datetime
import http.client as httplib

# Configurations for audio stream
form_1 = pyaudio.paInt16
channels = 1
samp_rate = 44100
chunk = 4096
record_secs = 3


def is_internet_connected():
    conn = httplib.HTTPSConnection("8.8.8.8", timeout=5)
    try:
        conn.request("HEAD", "/")
        return True
    except Exception:
        return False
    finally:
        conn.close()


def listener():
    # Start new pyaudio instance
    print("listening")
    audio = pyaudio.PyAudio()

    # Find the device index for the USB microphone or stop listening
    dev_index = None
    for index in range(audio.get_device_count()):
        name = audio.get_device_info_by_index(index).get('name')
        if name == "USB PnP Sound Device":
            dev_index = index
    if dev_index is None:
        dev_index = 1
        print("no usb microphone is connected, defaulting to dev_index = 1")

    # Opening the data stream to the microphone.
    stream = audio.open(
        format=form_1,
        rate=samp_rate,
        channels=channels,
        input_device_index=dev_index,
        input=True,
        frames_per_buffer=chunk
    )

    try:
        frames = []  # The array in which a current recording is stored in.
        threshold = 150  # The threshold from which the received sound data is recorded.
        previous_level = 0  # Helper variable to simulate an initial sound level of zero.

        def save_recording(frames_data):
            # Writing the .wav file.
            wav_output_filename = f'recordings/{uuid.uuid4()}.wav'
            wavefile = wave.open(wav_output_filename, 'wb')
            wavefile.setnchannels(channels)
            wavefile.setsampwidth(audio.get_sample_size(form_1))
            wavefile.setframerate(samp_rate)
            wavefile.writeframes(b''.join(frames_data))
            wavefile.close()

            if is_internet_connected():
                # Sending the file to the API
                with open(wav_output_filename, "rb") as file:
                    response = requests.post(
                        "https://dolphin-app-9sdeq.ondigitalocean.app/api/v1/recordings",
                        files={"recording": file}
                    )
                    print("sent local file to API")
                    print(response.text)

                    # Removing the locally stored sound file from storage.
                    os.remove(wav_output_filename)
                    print("deleted local file")
            else:
                # Write file information to .csv file
                with open("recordings_data.csv", "a") as csv_file:
                    writer = csv.writer(csv_file)

                    writer.writerow([
                        datetime.datetime.now(),
                        wav_output_filename
                    ])
                    print("saved file information to csv file")

        while True:
            data = stream.read(chunk, exception_on_overflow=False)  # Data sample coming from the microphone.
            frames.append(data)
            level = audioop.rms(data, 2)  # Volume level of the current data sample.

            print(level)

            # If the current volume exceeds the previously set threshold, save the sample to the current recording.
            if level >= threshold:
                frames.append(data)
                if threshold > previous_level:
                    print("started recording")

            # If the current volume is below the threshold, after the previous volume exceeded it, trigger the API call
            # to upload the current recording, and reset the frames variable.
            if previous_level >= threshold > level:
                save_recording(frames)
                frames = []

            # Store the current level in the previous level variable, to make it accessible in the next iteration.
            previous_level = level
    except KeyboardInterrupt:
        # When the script is interrupted, stop the stream, and the audio connection.
        save_recording(frames)
        stream.stop_stream()
        stream.close()
        audio.terminate()
        print("Shutdown requested...exiting")


if __name__ == '__main__':
    listener()
