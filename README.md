# Booking bot
a bot to help me book badminton courts so I don't need to stay up till midnight when they become available.
Also helps book courts in case someone cancels them. 

## Deployment
going to run this as a basic chron job

## Requirements
needs a config.toml with the user email and passord in the working directory.

## run
```
python main.py
```
## crontab
edit by running `crontab -e` to open the editor.
Place this line at the end to run the command every hour
```
0 * * * * uv run /home/roy/code/booking_bot/main.py 
```