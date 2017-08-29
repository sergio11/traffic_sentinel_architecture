package sanchez.sanchez.sergio.filter;

import org.apache.flink.api.common.functions.FilterFunction;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import sanchez.sanchez.sergio.datatypes.TaxiRide;
import sanchez.sanchez.sergio.utils.GeoUtils;

/**
 *
 * @author sergio
 */
public class NYCFilter implements FilterFunction<TaxiRide> {
    
    private static Logger logger = LoggerFactory.getLogger(NYCFilter.class);

    @Override
    public boolean filter(TaxiRide taxiRide) throws Exception {
        logger.info("Taxi Ride to Filter -> " + taxiRide.toString());
        return GeoUtils.isInNYC(taxiRide.getStartLon(), taxiRide.getStartLat()) &&
                    GeoUtils.isInNYC(taxiRide.getEndLon(), taxiRide.getEndLat());
    }
    
}
