package sanchez.sanchez.sergio.sink;

import java.util.HashMap;
import java.util.Map;
import org.apache.flink.api.common.functions.RuntimeContext;
import org.apache.flink.api.java.tuple.Tuple5;
import org.apache.flink.streaming.connectors.elasticsearch.ElasticsearchSinkFunction;
import org.apache.flink.streaming.connectors.elasticsearch.RequestIndexer;
import org.elasticsearch.action.index.IndexRequest;
import org.elasticsearch.client.Requests;
import sanchez.sanchez.sergio.config.DIPConfiguration;

/**
 * Inserts popular places into the "nyc-places" index.
 * @author sergio
 */
public class PopularPlaceInserter
        implements ElasticsearchSinkFunction<Tuple5<Float, Float, Long, Boolean, Integer>> {

    // construct index request
    @Override
    public void process(
            Tuple5<Float, Float, Long, Boolean, Integer> record,
            RuntimeContext ctx,
            RequestIndexer indexer) {

        // construct JSON document to index
        Map<String, String> json = new HashMap<>();
        json.put("time", record.f2.toString());         // timestamp
        json.put("location", record.f1 + "," + record.f0);  // lat,lon pair
        json.put("isStart", record.f3.toString());      // isStart
        json.put("cnt", record.f4.toString());          // count

        IndexRequest rqst = Requests.indexRequest()
                .index(DIPConfiguration.NYC_PLACES_INDEX) // index name
                .type(DIPConfiguration.POPULAR_LOCATIONS_MAPPING) // mapping name
                .source(json);

        indexer.add(rqst);
    }
}
