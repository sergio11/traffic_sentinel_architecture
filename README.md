# flink-stream-taxi-ride

Analyze the taxi ride event stream with Apache Flink

## Apache Flink Developed Jobs

### DataStream API - Popular Places

The task of the **“Popular Places”** job is to **identify popular places from the taxi ride data stream**. This is done by counting every five minutes the number of taxi rides that started and ended in the same area within the last 15 minutes. Arrival and departure locations should be separately counted. Only locations with more arrivals or departures than a provided popularity threshold should be forwarded to the result stream.

This task requires to **count taxi ride events by cell id and event type (start or end event)**. Hence, we need to obtain a cell id for each record and group the records by cell id and event type. Subsequently, we need to **define sliding time windows of 15 minutes length and 5 minutes evaluation interval.** In each window we count the number of events. The counts need to be filtered by the popularity threshold. Finally, the cell id should be converted back into longitude and latitude before the result stream is emitted. 

#### Steps needed to execute and view job results.

1. Create an index in elasticsearch called **"nyc-places"** from the web client Elastic HQ.

![Create an index in elasticsearch](https://raw.githubusercontent.com/sergio11/flink-stream-taxi-ride/master/src/main/resources/screenshot/create_index_places.png "Create an index in elasticsearch")

2. Create a schema mapping for the index (here called **popular-locations**):

```
curl -XPUT "http://192.168.0.55:9200/nyc-places/_mapping/popular-locations" -d'
{
 "popular-locations" : {
   "properties" : {
     "cnt": {"type": "integer"},
     "location": {"type": "geo_point"},
     "time": {"type": "date"},
     "isStart": {"type": "string"}
   }
 }
}'
```

3. You can check its definition in the detail pane of a Mapping in Elastic HQ.

![Verify Mapping on Elastic HQ](https://raw.githubusercontent.com/sergio11/flink-stream-taxi-ride/master/src/main/resources/screenshot/check_popular_locations_mapping.png "Verify Mapping on Elastic HQ")

4. Now you can upload and launch the job using the Apache Flink dashboard.

![Upload and Submit Job](https://raw.githubusercontent.com/sergio11/flink-stream-taxi-ride/master/src/main/resources/screenshot/upload_and_submit_job_apache_flink.png "Upload and Submit Job")

5. You can verify that the job has started running in the **"Running Jobs"** tab of the Apache Flink dashboard.

![Verify Job Execution](https://raw.githubusercontent.com/sergio11/flink-stream-taxi-ride/master/src/main/resources/screenshot/verify_job_execution.png "Verify Job Execution")






