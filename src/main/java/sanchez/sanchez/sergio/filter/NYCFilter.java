package sanchez.sanchez.sergio.filter;

import org.apache.flink.api.common.functions.FilterFunction;
import sanchez.sanchez.sergio.datatypes.TaxiRide;
import sanchez.sanchez.sergio.utils.GeoUtils;

/**
 *
 * @author sergio
 */
public class NYCFilter implements FilterFunction<TaxiRide> {

    @Override
    public boolean filter(TaxiRide taxiRide) throws Exception {
        return GeoUtils.isInNYC(taxiRide.getStartLon(), taxiRide.getStartLat()) &&
                    GeoUtils.isInNYC(taxiRide.getEndLon(), taxiRide.getEndLat());
    }
    
}
