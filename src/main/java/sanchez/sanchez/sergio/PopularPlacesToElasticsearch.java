package sanchez.sanchez.sergio;

import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.apache.flink.api.common.functions.FilterFunction;
import org.apache.flink.api.java.tuple.Tuple4;
import org.apache.flink.api.java.tuple.Tuple5;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.streaming.api.TimeCharacteristic;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import sanchez.sanchez.sergio.datatypes.TaxiRide;
import sanchez.sanchez.sergio.filter.NYCFilter;
import sanchez.sanchez.sergio.mapper.TaxiRideToGridCellAndEventTypeMapper;
import sanchez.sanchez.sergio.source.TaxiRideSource;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.connectors.elasticsearch2.ElasticsearchSink;
import sanchez.sanchez.sergio.config.DIPConfiguration;
import sanchez.sanchez.sergio.mapper.GridToCoordinatesMapper;
import sanchez.sanchez.sergio.sink.PopularPlaceInserter;
import sanchez.sanchez.sergio.window.RideCounter;

/**
 *
 * @author sergio

 * The program processes a stream of taxi ride events from the New York City Taxi and Limousine Commission (TLC).
 * It computes for each location the total number of persons that arrived by taxi.
 */
public class PopularPlacesToElasticsearch {
    
    private final static int POP_THRESHOLD = 20; // threshold for popular places
    private final static int MAX_EVENT_DELAY = 60; // events are out of order by max 60 seconds
    private final static int SERVING_SPEED_FACTOR = 600; // events of 10 minutes are served in 1 second
    
    public static void main(String[] args) throws Exception {
        
        // read parameters
        ParameterTool params = ParameterTool.fromArgs(args);
        String input = params.getRequired("input");

        // set up streaming execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setStreamTimeCharacteristic(TimeCharacteristic.EventTime);
        
        // Add event souce
        DataStream<TaxiRide> rides = env.addSource(
				new TaxiRideSource(input, MAX_EVENT_DELAY, SERVING_SPEED_FACTOR));
        
        
        // find popular places
        DataStream<Tuple5<Float, Float, Long, Boolean, Integer>> popularPlaces = rides
            // remove all rides which are not within NYC
            .filter(new NYCFilter())
            // match ride to grid cell and event type (start or end)
            .map(new TaxiRideToGridCellAndEventTypeMapper())
            // partition by cell id and event type
            .keyBy(0, 1)
            // build sliding window
            .timeWindow(Time.minutes(15), Time.minutes(5))
            // count ride events in window
            .apply(new RideCounter())
            // filter by popularity threshold
            .filter(new FilterFunction<Tuple4<Integer, Long, Boolean, Integer>>() {
                @Override
                public boolean filter(Tuple4<Integer, Long, Boolean, Integer> count) throws Exception {
                    return count.f3 >= POP_THRESHOLD;
                }
            })
            // map grid cell to coordinates
            .map(new GridToCoordinatesMapper());
        
        
        Map<String, String> config = new HashMap<>();
        // This instructs the sink to emit after every element, otherwise they would be buffered
        config.put(DIPConfiguration.BULK_FLUSH_MAX_ACTIONS, "10");
	config.put(DIPConfiguration.CLUSTER_NAME, "elasticsearch");

	List<InetSocketAddress> transports = new ArrayList<>();
	transports.add(new InetSocketAddress(
                InetAddress.getByName(DIPConfiguration.ELASTICSEARCH_HOSTNAME),
                DIPConfiguration.ELASTICSEARCH_PORT));

        popularPlaces.addSink(new ElasticsearchSink<>(config, transports, new PopularPlaceInserter()));
        
        // execute the transformation pipeline
        env.execute("Popular Places to Elasticsearch");
    }
    
}
