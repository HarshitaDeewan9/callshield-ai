package in.callshield.gateway;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.security.Principal;
import java.util.Map;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.*;
@RestController @RequestMapping("/api/live")
public class LiveController {
    final AiClient ai; final RecordService saved;
    public LiveController(AiClient ai,RecordService saved){this.ai=ai;this.saved=saved;}
    @PostMapping("/sessions") @ResponseStatus(HttpStatus.CREATED)
    JsonNode create(@RequestBody JsonNode body,Principal p) {
        JsonNode response=ai.request("POST","/api/v2/sessions",body);
        String id=response.path("sessionId").asText();java.util.UUID.fromString(id);
        saved.records.save(new AnalysisRecord(id,saved.owner(p),"LIVE",response.toString()));
        ((ObjectNode)response).put("websocketPath","/ws/live/"+id).put("recordId",id);
        return response;
    }
    @GetMapping("/sessions/{id}") JsonNode snapshot(@PathVariable String id,Principal p) {
        var record=saved.owned(id,saved.owner(p));
        return ai.request("GET","/api/v2/sessions/"+record.id,null);
    }
}
