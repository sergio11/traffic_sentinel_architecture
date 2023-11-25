FROM apache/nifi:1.12.0
COPY ./templates/Nifi_Traffic_Sentinel_Smart_Highway_Net_v2.xml /opt/nifi/nifi-current/conf/templates
COPY --chown=nifi:nifi flow.xml.gz /opt/nifi/nifi-current/conf/
EXPOSE 8080
