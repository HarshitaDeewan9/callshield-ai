package in.callshield.gateway;
import java.util.Optional;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.domain.Pageable;
public interface RecordRepository extends JpaRepository<AnalysisRecord,String> {
    Optional<AnalysisRecord> findByIdAndOwnerId(String id,String ownerId);
    List<AnalysisRecord> findByOwnerIdOrderByCreatedAtDesc(String ownerId,Pageable pageable);
}
