import requests
import pandas as pd
from datetime import date,datetime
year,month,date = '2026','07','31'
business_date=f"{year}-{month}-{date}"
door_name="north"
base_url="http://127.0.0.1:8002"
get_url=f"{base_url}/door-visits?open_date={business_date}&door_name={door_name}"

response_dict=requests.get(get_url).json()

print(response_dict["sensor_visits"])


df=pd.DataFrame(response_dict["sensor_visits"]["datas"])
df['open_date']=business_date
df['TEC_CREATION_TS'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
date_id=int(business_date.split("-")[0]+business_date.split("-")[1]+business_date.split("-")[2])
df.insert(0,'door_name',door_name)
df.insert(0,'date_id',date_id)
