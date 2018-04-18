# The MIT License (MIT)
# Copyright (c) 2016 Dell Inc. or its subsidiaries.

# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
Sample Script to show graphing of performanc metrics using matplotlib

"""
import PyU4V
import datetime as dt
import time
import numpy as np
import json
from influxdb import InfluxDBClient

# end_date = current time in milliseconds.
# start_date sets to current time - 15 min.
end_date = int(round(time.time()) * 1000)
start_date = (end_date - 900000)

# InfluxDB connection details
dbhost = 'localhost'
dbport = 8086
dbuser = 'root'
dbpassword = 'root'
dbname = 'vmaxdb'

# Example using a single VMAX SN
vmaxsn = ''
vmaxip = ''
vmaxport = '8443'
vmaxuser = 'smc'
vmaxpasswd = 'smc'
vmaxverify = False

# Example adding a location tag to Influx DB
location = "Boston, MA"

def insert_metrics(dbclient, metrics, measurement_name, additional_tags = {}):
    """Inserts metrics pulled into InfluxDB database.
    :param dbclient: InfluxDB connector
    :param metrics: dictionary of metrics to insert
    :param measurement_name: name of the measurement value
    :param additional_tags: additional tags for the measurement
    """

    for metric_values in metrics.get('perf_data'):

        # Converts UTC epoch timestamp to InfluxDB format
        epochtime = (metric_values.get ('timestamp'))
        convtime = dt.datetime.utcfromtimestamp(epochtime/1000)
        timeformat = convtime.strftime("%Y-%m-%dT%H:%M:%S")

        # Default tags and any additional tags are added.
        tags = {'S/N' : vmaxsn, 'Location' : location}
        tags.update(additional_tags)

        # InfluxDB JSON format
        db_json = {
            "measurement" : measurement_name,
            "tags" : tags,
            "fields" : metric_values,
            "time" : timeformat
        }

        # Inserts the metric into InfluxDB database
        dbvalue = []
        dbvalue.append(db_json.copy())
        dbclient.write_points(dbvalue)

def main():
    ru = PyU4V.U4VConn(username=vmaxuser, password=vmaxpasswd,  \
        server_ip=vmaxip, port=vmaxport, verify=vmaxverify, u4v_version='84')
    ru.set_array_id(vmaxsn)

    dbclient = InfluxDBClient(dbhost, dbport, dbuser, dbpassword, dbname)

    array_metrics = ru.performance.get_array_metrics(start_date, end_date)
    insert_metrics(dbclient, array_metrics, "Array")

    sg_list = ru.provisioning.get_storage_group_list()

    for sg_id in sg_list:
        sg_metrics = ru.performance.get_storage_group_metrics(sg_id, \
            start_date, end_date)
        insert_metrics(dbclient, sg_metrics, "Storage Group", \
            {"Storage Group" : sg_id})

    director_list = ru.provisioning.get_director_list()

    for director_id in director_list:
        director_metrics = ru.performance.get_director_info(director_id, \
            start_date, end_date)
        director_tags = {"Director ID" : director_id, \
            "Director Type" : director_metrics['directorType']}
        insert_metrics(dbclient, director_metrics, "Director", director_tags)

    pg_list = ru.provisioning.get_portgroup_list()

    for pg_id in pg_list:
        pg_metrics = ru.performance.get_port_group_metrics(pg_id, start_date, \
            end_date)
        insert_metrics(dbclient, pg_metrics, "Port Group", \
            {"Port Group" : pg_id})

    host_list = ru.provisioning.get_host_list()

    for host_id in host_list:
        host_metrics = ru.performance.get_host_metrics(host_id, start_date, \
            end_date)
        insert_metrics(dbclient, host_metrics, "Host", {"Host" : host_id})


    array_time = array_metrics['perf_data'][-1]['timestamp']
    convtime = dt.datetime.utcfromtimestamp(array_time/1000)
    timeformat = convtime.strftime("%Y-%m-%dT%H:%M:%S")

    srp_list = ru.provisioning.get_srp_list()

    for srp_id in srp_list:
        srp_metrics = ru.provisioning.get_srp(srp_id)
        srp_cleanup = []

        for type_check in srp_metrics:
            if type(srp_metrics[type_check]) is list:
                srp_cleanup.append(type_check)

        for i in srp_cleanup:
            srp_metrics.pop(i, None)

        array_free_capacity = srp_metrics['total_usable_cap_gb'] - srp_metrics['total_allocated_cap_gb']
        array_free_percent = array_free_capacity / srp_metrics['total_usable_cap_gb']

        srp_metrics['array_free_capacity'] = array_free_capacity
        srp_metrics['array_free_percent'] = array_free_percent

        db_json = {
            "measurement" : "SRP",
            "tags" : {
                "S/N" : vmaxsn,
                "Location" : location,
                "SRP" : srp_id
            },
            "fields" : srp_metrics,
            "time" : timeformat
        }

        dbvalue = []
        dbvalue.append(db_json.copy())
        dbclient.write_points(dbvalue)

    alerts_count = {}

    alerts_fatal = ru.common.get_resource(
        ru.array_id, 'system', 'alert', params={'severity' : 'FATAL'})
    alerts_critical = ru.common.get_resource(
        ru.array_id, 'system', 'alert', params={'severity' : 'CRITICAL'})

    alerts_count['alerts_fatal_critical'] = len(alerts_fatal['alertId']) + len(alerts_critical['alertId'])

    alerts_warning = ru.common.get_resource(
        ru.array_id, 'system', 'alert', params={'severity' : 'WARNING'})
    alerts_minor = ru.common.get_resource(
        ru.array_id, 'system', 'alert', params={'severity' : 'MINOR'})

    alerts_count['alerts_minor_warning'] = len(alerts_warning['alertId']) + len(alerts_minor['alertId'])

    alerts_info = ru.common.get_resource(
        ru.array_id, 'system', 'alert', params={'severity' : 'INFORMATION'})

    alerts_count['alerts_information'] = len(alerts_info['alertId'])

    db_json = {
        "measurement" : "Alerts",
        "tags" : {
            "S/N" : vmaxsn,
            "Location" : location
        },
        "fields" : alerts_count,
        "time" : timeformat
    }

    dbvalue = []
    dbvalue.append(db_json.copy())
    dbclient.write_points(dbvalue)

main()
