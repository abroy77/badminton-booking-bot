# Booking bot
a bot to help me book badminton courts so I don't need to stay up till midnight when they become available.
Also helps book courts in case someone cancels them. 

## Deployment
going to run this as a basic cron job

## Requirements
needs a config.toml with the user email and passord.
The config file must have these elements:
```
[login-credentials]
email = "user@email.com"
password = "VerySecurePassword"
[paths]
booking_logs = "<path/to/booking/logs.txt>"
```
The `booking_logs` item is a path to a text file where the booked courts are stored.
This file is created if it does not exist, and overwritten if it does.

[uv](https://docs.astral.sh/uv/) is the recommended package manager to set up the dev environment. but anything that works with `pyproject.toml` is okay like `poetry`.


## run
If you don't want to bother making a venv I would suggest installing [uv](https://docs.astral.sh/uv/)
and running the following command. It will install python and other dependencies for you.
```
uv run main.py </path/to/config>.toml
```
To set up the project to work on it yourself run `uv sync`

## crontab
edit by running `crontab -e` to open the editor.
Place this line at the end to run the command every hour
```
1 * * * * </path/to/python/> </path/to/main>.py </path/to/config.toml> >> </path/to/logfile.txt>
```
