# DX Alert Demo

DX Alert Demo is a Flask application which authenticates a Dropbox account and listens for events on a Dropbox app folder and sends out email alerts for the configured email ids.

## Installation

DX Alert Demo requires a Python environment with Flask to run.

### (Optional) Miniconda setup if you don't have a Python environment

- Download miniconda for Python 2.7 from [Miniconda site](https://conda.io/miniconda.html) according to your system specifications.
- If you're on Linux or Mac, this will be a bash script. Run the same using the following command-
```sh
$ bash Miniconda3-latest-MacOSX-x86_64.sh
or 
$ bash Miniconda3-latest-Linux-x86_64.sh
```
Now close and re-open your terminal window for the changes to take effect.

- Setup a conda environment:
```sh
$ conda create -n flask_env Flask
```

This will create virtual environment with Flask installed. Activate this environment:
```sh
$ source activate flask_env
```
Install other dependencies using the requirements file in the app folder:
```sh
$ pip install -r requirements.txt
```

Note: You can also use 'virtualenv' to create a virtual environment and install the requirements.

### Creating a Dropbox App

DX Alert Demo requires an app to be created in the Dropbox developer console.

- Go to [Dropbox Developer console](https://www.dropbox.com/developers/apps) and click on "Create app" 
- Select "Dropbox API" under Choose an API
- Select "App folder" under Choose the type of access you need (You can choose 'Full Dropbox' to get access to all the folders of the user)
- Give a name to your app. This has certain [guidelines](https://www.dropbox.com/developers/reference/branding-guide) to be followed.
- Click on "Create app"
- Note down the "App key" and "App secret" to be used later.


### Running the app

Setup Flask app:

Open "config_file.cfg" and edit the values of APP_KEY and APP_SECRET you noted down in the previous step.

Enter following commands in the terminal window where you activated the flask environment to run the app:
```sh
$ EXPORT FLASK_APP=app
$ EXPORT FLASK_DEBUG=1 # (optional) to enable debug mode, also for not restarting the server after every change
$ flask initdb # initialises the Database
$ flask run
```
This will start a very simple built-in server of flask on your localhost with port 5000.

Download and setup ngrok:

ngrok is a tool which provides a publicly available URL for your localhost instance.
ngrok is required since the webhook and redirect URI to be configured on Dropbox require a publicly available URL.

- Download [ngrok](https://ngrok.com/download) according to your system specifications.
- Unzip it to find a single executable binary
- Run the following command in a new terminal window to run ngrok
```sh
$ ./ngrok http 5000
```
This will start ngrok service and provide you with a publicly available URL whcih forwards requests to your localhost web server running on port 5000.

Make a note of the https url next to the heading 'Forwarding'. Ex- https://6c2c3989.ngrok.io

### Setup Dropbox Redirect URI and Webhook URI

- Go back to your app settings page on the Dropbox developer console
- Add the ngrok url you obtained in the previous step to webhook and redirect_uri as shown in example below-
    - Webhook URI - <https_ngrok_url>/webhook
    - Redirect URI - <https_ngrok_url>/oauth_callback

### Usage of app
- Go to the ngrok URL <https_ngrok_url> on your web browser
- You should see a text field for email and a button 'Connect to Dropbox'
- Enter the email id which needs to be configured for alerts in the text field and click on 'Connect to Dropbox'
- If you're not logged in to dropbox, then you would get a prompt to sign in to dropbox and then allow access to this app as part of the Oauth flow. Sign In and allow access to the app.
- You will be redirected to the configure page where you can see your email configured to receive alerts.
- If you had chosen "App folder" as access type in Dropbox app setting, then you will have a new folder under Apps folder in your Dropbox account. This would be the folder which will trigger email alerts on any file actions. If you had chosen 'Full dropbox access', then any file changes in your dropbox account will trigger an email alert.
- Upload a new file or delete a file to trigger email alerts.
- You can disable the email alerts by selecting 'No' in the dropdown under the heading 'Alert enabled?' and clicking on 'Submit' button.
