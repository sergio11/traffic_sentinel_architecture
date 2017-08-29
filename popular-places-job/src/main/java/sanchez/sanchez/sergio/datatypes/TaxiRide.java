
package sanchez.sanchez.sergio.datatypes;

import java.util.Locale;
import org.joda.time.DateTime;
import org.joda.time.format.DateTimeFormat;
import org.joda.time.format.DateTimeFormatter;

/**
 *
 * @author sergio
 * 
 * A TaxiRide is a taxi ride event. There are two types of events, a taxi ride start event and a
 * taxi ride end event. The isStart flag specifies the type of the event.
 *
 * A TaxiRide consists of
 * - the rideId of the event which is identical for start and end record
 * - the time of the event
 * - the longitude of the start location
 * - the latitude of the start location
 * - the longitude of the end location
 * - the latitude of the end location
 * - the passengerCnt of the ride
 * - the travelDistance which is -1 for start events
 *
 */
public class TaxiRide {
    
    private static transient DateTimeFormatter timeFormatter =
        DateTimeFormat.forPattern("yyyy-MM-dd HH:mm:ss").withLocale(Locale.US).withZoneUTC();
    
    private long rideId;
    private boolean isStart;
    private DateTime startTime;
    private DateTime endTime;
    private float startLon;
    private float startLat;
    private float endLon;
    private float endLat;
    private short passengerCnt;
    
    public TaxiRide() {}

    public TaxiRide(long rideId, boolean isStart, DateTime startTime, DateTime endTime, float startLon, float startLat, float endLon, float endLat, short passengerCnt) {
        this.rideId = rideId;
        this.isStart = isStart;
        this.startTime = startTime;
        this.endTime = endTime;
        this.startLon = startLon;
        this.startLat = startLat;
        this.endLon = endLon;
        this.endLat = endLat;
        this.passengerCnt = passengerCnt;
    }

    public static DateTimeFormatter getTimeFormatter() {
        return timeFormatter;
    }

    public static void setTimeFormatter(DateTimeFormatter timeFormatter) {
        TaxiRide.timeFormatter = timeFormatter;
    }

    public long getRideId() {
        return rideId;
    }

    public void setRideId(long rideId) {
        this.rideId = rideId;
    }

    public boolean isStart() {
        return isStart;
    }

    public void setIsStart(boolean isStart) {
        this.isStart = isStart;
    }

    public DateTime getStartTime() {
        return startTime;
    }

    public void setStartTime(DateTime startTime) {
        this.startTime = startTime;
    }

    public DateTime getEndTime() {
        return endTime;
    }

    public void setEndTime(DateTime endTime) {
        this.endTime = endTime;
    }

    public float getStartLon() {
        return startLon;
    }

    public void setStartLon(float startLon) {
        this.startLon = startLon;
    }

    public float getStartLat() {
        return startLat;
    }

    public void setStartLat(float startLat) {
        this.startLat = startLat;
    }

    public float getEndLon() {
        return endLon;
    }

    public void setEndLon(float endLon) {
        this.endLon = endLon;
    }

    public float getEndLat() {
        return endLat;
    }

    public void setEndLat(float endLat) {
        this.endLat = endLat;
    }

    public short getPassengerCnt() {
        return passengerCnt;
    }

    public void setPassengerCnt(short passengerCnt) {
        this.passengerCnt = passengerCnt;
    }
    
    
    @Override
    public boolean equals(Object other) {
        return other instanceof TaxiRide
                && this.rideId == ((TaxiRide) other).rideId;
    }

    @Override
    public int hashCode() {
        return (int) this.rideId;
    }
    
    public String toString() {
        StringBuilder sb = new StringBuilder();
        sb.append(rideId).append(",");
        sb.append(isStart ? "START" : "END").append(",");
        if (isStart) {
            sb.append(startTime.toString(timeFormatter)).append(",");
            sb.append(endTime.toString(timeFormatter)).append(",");
        } else {
            sb.append(endTime.toString(timeFormatter)).append(",");
            sb.append(startTime.toString(timeFormatter)).append(",");
        }
        sb.append(startLon).append(",");
        sb.append(startLat).append(",");
        sb.append(endLon).append(",");
        sb.append(endLat).append(",");
        sb.append(passengerCnt);

        return sb.toString();
    }
    
    public static TaxiRide fromString(String line) {

        String[] tokens = line.split(",");
        if (tokens.length != 9) {
            throw new RuntimeException("Invalid record: " + line);
        }

        TaxiRide ride = new TaxiRide();

        try {
            ride.rideId = Long.parseLong(tokens[0]);

            switch (tokens[1]) {
                case "START":
                    ride.isStart = true;
                    ride.startTime = DateTime.parse(tokens[2], timeFormatter);
                    ride.endTime = DateTime.parse(tokens[3], timeFormatter);
                    break;
                case "END":
                    ride.isStart = false;
                    ride.endTime = DateTime.parse(tokens[2], timeFormatter);
                    ride.startTime = DateTime.parse(tokens[3], timeFormatter);
                    break;
                default:
                    throw new RuntimeException("Invalid record: " + line);
            }

            ride.startLon = tokens[4].length() > 0 ? Float.parseFloat(tokens[4]) : 0.0f;
            ride.startLat = tokens[5].length() > 0 ? Float.parseFloat(tokens[5]) : 0.0f;
            ride.endLon = tokens[6].length() > 0 ? Float.parseFloat(tokens[6]) : 0.0f;
            ride.endLat = tokens[7].length() > 0 ? Float.parseFloat(tokens[7]) : 0.0f;
            ride.passengerCnt = Short.parseShort(tokens[8]);

        } catch (NumberFormatException nfe) {
            throw new RuntimeException("Invalid record: " + line, nfe);
        }

        return ride;
    }
    
}
