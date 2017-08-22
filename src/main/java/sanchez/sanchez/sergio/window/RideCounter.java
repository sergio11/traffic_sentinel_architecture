package sanchez.sanchez.sergio.window;

import org.apache.flink.api.java.tuple.Tuple;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.tuple.Tuple4;
import org.apache.flink.streaming.api.functions.windowing.WindowFunction;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

/**
 * Counts the number of rides arriving or departing.
 * @author sergio
 */
public class RideCounter implements WindowFunction<
        Tuple2<Integer, Boolean>, // input type
        Tuple4<Integer, Long, Boolean, Integer>, // output type
        Tuple, // key type
        TimeWindow> // window type
{

    @SuppressWarnings("unchecked")
    @Override
    public void apply(
            Tuple key,
            TimeWindow window,
            Iterable<Tuple2<Integer, Boolean>> gridCells,
            Collector<Tuple4<Integer, Long, Boolean, Integer>> out) throws Exception {

        int cellId = ((Tuple2<Integer, Boolean>) key).f0;
        boolean isStart = ((Tuple2<Integer, Boolean>) key).f1;
        long windowTime = window.getEnd();

        int cnt = 0;
        for (Tuple2<Integer, Boolean> c : gridCells) {
            cnt += 1;
        }

        out.collect(new Tuple4<>(cellId, windowTime, isStart, cnt));
    }
}
