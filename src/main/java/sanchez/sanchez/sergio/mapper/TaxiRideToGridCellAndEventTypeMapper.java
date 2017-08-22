/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package sanchez.sanchez.sergio.mapper;

import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.api.java.tuple.Tuple2;
import sanchez.sanchez.sergio.datatypes.TaxiRide;
import sanchez.sanchez.sergio.utils.GeoUtils;

/**
 *
 * @author sergio
 */
public class TaxiRideToGridCellAndEventTypeMapper  implements MapFunction<TaxiRide, Tuple2<Integer, Boolean>> {

    @Override
    public Tuple2<Integer, Boolean> map(TaxiRide taxiRide) throws Exception {
        return new Tuple2<>(
                GeoUtils.mapToGridCell(taxiRide.getStartLon(), taxiRide.getStartLat()),
                taxiRide.isStart()
        );
    }
    
}
