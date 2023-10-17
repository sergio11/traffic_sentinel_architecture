package com.dreamsoftware.integrator.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class CameraFogFrameDTO {

    @JsonProperty("mac_address")
    private String macAddress;

    @JsonProperty("timestamp")
    private String timestamp;

    @JsonProperty("frame_data")
    private String frameData;
}
