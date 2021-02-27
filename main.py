import requests
import json
import pandas as pd
from tabulate import tabulate

vendor_col_name = "vendor"
state_col_name = "state"
fully_booked_col_name = "fully_booked"
city_col_name = "city"
link_col_name = "link"


def fetch_cvs_vaccine_data(state, results_df):
    print("Fetching CVS vaccine info for " + state)
    url = "https://www.cvs.com/immunizations/covid-19-vaccine.vaccine-status." + state + ".json?vaccineinfo"
    headers = {"referer": "https://www.cvs.com/immunizations/covid-19-vaccine"}
    r = requests.get(url, headers=headers)
    parsedResponse = json.loads(r.text)
    # print("The status code after hitting csv is " + r.status_code)
    state_info = parsedResponse["responsePayloadData"]["data"][state]
    fully_booked = True
    for city_info in state_info:
        if city_info["status"] != "Fully Booked":
            results_df = results_df.append({
                vendor_col_name: "CVS",
                state_col_name: state,
                city_col_name: city_info["city"],
                link_col_name: "https://www.cvs.com/vaccine/intake/store/covid-screener/covid-qns",
                fully_booked_col_name: False,
            }, ignore_index=True)
            if fully_booked:
                fully_booked = False
    if fully_booked:
        results_df = results_df.append({
            vendor_col_name: "CVS",
            state_col_name: state,
            fully_booked_col_name: True
        }, ignore_index=True)
        print("CVS is fully booked in all cities")
    return results_df

if __name__ == '__main__':
    print("Starting program...")
    results_df = pd.DataFrame({
        vendor_col_name: pd.Series([], dtype='str'),
        state_col_name: pd.Series([], dtype='str'),
        fully_booked_col_name: pd.Series([], dtype='bool'),
        city_col_name: pd.Series([], dtype='str'),
        link_col_name: pd.Series([], dtype='str')})
    print("Fetching data for CVS...")
    results_df = fetch_cvs_vaccine_data("NY", results_df)
    results_df = fetch_cvs_vaccine_data("NJ", results_df)
    results_df = fetch_cvs_vaccine_data("VA", results_df)
    print("Printing open appointments dataset")
    print(tabulate(results_df, headers='keys', tablefmt='psql'))
