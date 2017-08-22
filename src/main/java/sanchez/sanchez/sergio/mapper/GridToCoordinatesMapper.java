package sanchez.sanchez.sergio.mapper;

import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.api.java.tuple.Tuple4;
import org.apache.flink.api.java.tuple.Tuple5;
import sanchez.sanchez.sergio.utils.GeoUtils;

/**
 * Maps the grid cell id back to longitude and latitude coordinates.
 * @author sergio
 */
public class GridToCoordinatesMapper implements
        MapFunction<Tuple4<Integer, Long, Boolean, Integer>, Tuple5<Float, Float, Long, Boolean, Integer>> {

    @Override
    public Tuple5<Float, Float, Long, Boolean, Integer> map(
            Tuple4<Integer, Long, Boolean, Integer> cellCount) throws Exception {

        return new Tuple5<>(
                GeoUtils.getGridCellCenterLon(cellCount.f0),
                GeoUtils.getGridCellCenterLat(cellCount.f0),
                cellCount.f1,
                cellCount.f2,
                cellCount.f3);
    }
}
