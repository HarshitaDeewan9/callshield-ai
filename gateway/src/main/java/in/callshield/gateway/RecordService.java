package in.callshield.gateway;
import com.fasterxml.jackson.databind.*;
import java.security.Principal;
import java.time.Instant;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
@Service
public class RecordService {
    final AccountRepository accounts; final RecordRepository records; final ObjectMapper json;
    public RecordService(AccountRepository a,RecordRepository r,ObjectMapper j) {accounts=a;records=r;json=j;}
    public String owner(Principal principal) {return accounts.findByEmail(principal.getName()).orElseThrow().id;}
    public AnalysisRecord owned(String id,String owner) {return records.findByIdAndOwnerId(id,owner).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Report not found."));}
    public AnalysisRecord save(String owner,String kind,JsonNode payload) {var record=new AnalysisRecord(UUID.randomUUID().toString(),owner,kind,payload.toString());return records.save(record);}
    public JsonNode payload(AnalysisRecord record) {try{return json.readTree(record.payload);}catch(Exception e){throw new IllegalStateException("Unreadable saved report");}}
    public Map<String,Object> view(AnalysisRecord record) {return Map.of("id",record.id,"kind",record.kind,"createdAt",record.createdAt.toString(),"result",payload(record));}
}
