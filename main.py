import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import yaml
import pandas as pd
import requests
from tabulate import tabulate
import os.path
from os import path

vendor_col_name = "vendor"
state_col_name = "state"
appts_available_col_name = "appointment_available"
city_col_name = "city"
address_col_name = "address"
phone_col_name = "phone"
notes_col_name = "notes"
link_col_name = "link"


def fetch_riteaid_vaccine_data(riteaid_config, results_df):
    for zip_config in riteaid_config:
        results_df = fetch_riteaid_vaccine_data_by_zip(
            str(zip_config["zip"]),
            str(zip_config["radius"]),
            results_df)
    return results_df


def fetch_riteaid_vaccine_data_by_zip(zip, radius, results_df):
    print("Fetching RiteAid vaccine info for the closest 10 stores within a " + radius + " mile radius of " + zip)
    url = "https://www.riteaid.com/services/ext/v2/stores/getStores?" \
          "address=" + zip + "&attrFilter=PREF-112&radius=" + radius
    stores_response = requests.get(url)
    parsed_stores = json.loads(stores_response.text)
    for store_info in parsed_stores["Data"]["stores"]:
        store_num = store_info["storeNumber"]
        store_vaccine_url = "https://www.riteaid.com/services/ext/v2/vaccine/checkSlots?storeNumber=" + str(store_num)
        store_vaccine_response = requests.get(store_vaccine_url)
        parsed_store_vacciene_response = json.loads(store_vaccine_response.text)
        slot_one_available = parsed_store_vacciene_response["Data"]["slots"]["1"]
        slot_two_available = parsed_store_vacciene_response["Data"]["slots"]["2"]
        results_df = results_df.append({
            vendor_col_name: "RiteAid",
            state_col_name: store_info["state"],
            city_col_name: store_info["city"],
            address_col_name: store_info["address"],
            phone_col_name: store_info["fullPhone"],
            link_col_name: "https://www.riteaid.com/pharmacy/covid-qualifier",
            appts_available_col_name: slot_one_available or slot_two_available,
            notes_col_name: "slot one is " + str(slot_one_available) + " and slot two is " + str(slot_two_available)
        }, ignore_index=True)
    return results_df


def fetch_cvs_vaccine_data(cvs_config, results_df):
    cvs_states = cvs_config["states"]
    for state in cvs_states:
        results_df = fetch_cvs_vaccine_data_by_state(state, results_df)
    return results_df


def fetch_cvs_vaccine_data_by_state(state, results_df):
    print("Fetching CVS vaccine info for " + state)
    url = "https://www.cvs.com/immunizations/covid-19-vaccine.vaccine-status." + state + ".json?vaccineinfo"
    headers = {"referer": "https://www.cvs.com/immunizations/covid-19-vaccine"}
    r = requests.get(url, headers=headers)
    parsedResponse = json.loads(r.text)
    state_info = parsedResponse["responsePayloadData"]["data"][state]
    for city_info in state_info:
        results_df = results_df.append({
            vendor_col_name: "CVS",
            state_col_name: state,
            city_col_name: city_info["city"],
            link_col_name: "https://www.cvs.com/vaccine/intake/store/covid-screener/covid-qns",
            appts_available_col_name: city_info["status"] != "Fully Booked",
        }, ignore_index=True)
    return results_df


def send_email(email_config, appointments_df, results_df):
    msg = MIMEMultipart()
    msg['Subject'] = "Covid Vaccine Notifications!"
    msg['From'] = email_config["sender"]["email"]
    html_attmt = """\
    <html>
      <head></head>
      <body>
        <h1>The first table shows places where appointments are available</h1>
        <div>
            {0}
        </div>
        
        <h1>The second table shows organizations that we searched</h1>
        <div>
            {1}
        </div>
      </body>
    </html>
    """.format(appointments_df.to_html(), results_df.to_html())
    mime_text = MIMEText(html_attmt, 'html')
    msg.attach(mime_text)

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(email_config["sender"]["email"], email_config["sender"]["password"])
    server.sendmail(msg['From'], email_config["recipients"], msg.as_string())
    server.quit()


def get_config():
    with open(r'config.yml') as file:
        config = yaml.load(file, Loader=yaml.FullLoader)
        return config


def get_prev_appointments_df():
    if not path.exists('apointments_df.csv'):
        return pd.DataFrame({
            vendor_col_name: pd.Series([], dtype='str'),
            state_col_name: pd.Series([], dtype='str'),
            appts_available_col_name: pd.Series([], dtype='bool'),
            city_col_name: pd.Series([], dtype='str'),
            address_col_name: pd.Series([], dtype='str'),
            phone_col_name: pd.Series([], dtype='str'),
            notes_col_name: pd.Series([], dtype='str'),
            link_col_name: pd.Series([], dtype='str')})
    return pd.read_csv('apointments_df.csv', index_col=0)


if __name__ == '__main__':
    print("Starting program...")
    results_df = pd.DataFrame({
        vendor_col_name: pd.Series([], dtype='str'),
        state_col_name: pd.Series([], dtype='str'),
        appts_available_col_name: pd.Series([], dtype='bool'),
        city_col_name: pd.Series([], dtype='str'),
        address_col_name: pd.Series([], dtype='str'),
        phone_col_name: pd.Series([], dtype='str'),
        notes_col_name: pd.Series([], dtype='str'),
        link_col_name: pd.Series([], dtype='str')})
    print("Reading config...")
    config = get_config()
    datasources_config = config["datasources"]
    print("Fetching data for CVS...")
    results_df = fetch_cvs_vaccine_data(datasources_config["cvs"], results_df)
    print("Fetching data for Rite Aid... ")
    results_df = fetch_riteaid_vaccine_data(datasources_config["riteaid"], results_df)
    print("Printing full dataset...")
    print(tabulate(results_df, headers='keys', tablefmt='psql'))
    print("Printing previous open appointments dataset...")
    prev_appointments_df = get_prev_appointments_df()
    print(tabulate(prev_appointments_df, headers='keys', tablefmt='psql'))
    print("Printing open appointments dataset...")
    open_appointments_df = results_df[(results_df[appts_available_col_name] == True)]
    print(tabulate(open_appointments_df, headers='keys', tablefmt='psql'))
    # send email if there are open appointments
    # make sure that you have a file called config.yml that has actual senders and recipients configured!
    email_config = config["email"]
    if not open_appointments_df.empty and not open_appointments_df.equals(prev_appointments_df):
        open_appointments_df.to_csv('apointments_df.csv')
        send_email(email_config, open_appointments_df, results_df)
