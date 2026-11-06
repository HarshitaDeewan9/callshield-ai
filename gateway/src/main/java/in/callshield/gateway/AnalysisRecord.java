package in.callshield.gateway;
import jakarta.persistence.*;
import java.time.Instant;
@Entity @Table(name="analysis_records")
public class AnalysisRecord {
    @Id public String id;
    @Column(name="owner_id",nullable=false) public String ownerId;
    @Column(nullable=false) public String kind;
    @Column(nullable=false,columnDefinition="TEXT") public String payload;
    @Column(name="created_at",nullable=false) public Instant createdAt;
    protected AnalysisRecord() {}
    public AnalysisRecord(String id,String owner,String kind,String payload) {
        this.id=id; ownerId=owner; this.kind=kind; this.payload=payload; createdAt=Instant.now();
    }
}
