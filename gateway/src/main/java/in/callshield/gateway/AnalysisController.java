package in.callshield.gateway;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.Principal;
import java.util.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.data.domain.PageRequest;
@RestController @RequestMapping("/api")
public class AnalysisController {
    record TextInput(@NotBlank @Size(max=3000) String transcript,@Pattern(regexp="en-IN|hi-IN|hi-Latn|bn-IN|te-IN|ta-IN|mr-IN|gu-IN|kn-IN|ml-IN|or-IN|pa-IN") String inputLanguage,@Pattern(regexp="en-IN|hi-IN|hi-Latn|bn-IN|te-IN|ta-IN|mr-IN|gu-IN|kn-IN|ml-IN|or-IN|pa-IN") String explanationLanguage) {}
    record WarningInput(@Pattern(regexp="en-IN|hi-IN") String language) {}
    final AiClient ai;final RecordService saved;final ObjectMapper json;final LiveSocket live;
    public AnalysisController(AiClient a,RecordService s,ObjectMapper j,LiveSocket l){ai=a;saved=s;json=j;live=l;}
    @GetMapping("/health") Map<String,String> health(){return Map.of("status","alive");}
    @GetMapping("/capabilities") JsonNode capabilities(){return ai.request("GET","/api/v1/capabilities",null);}
    @GetMapping("/ready") JsonNode ready(){return ai.request("GET","/health/ready",null);}
    @PostMapping("/analyze/text") Map<String,Object> text(@Valid @RequestBody TextInput input,Principal principal) {
        var body=json.createObjectNode().put("inputLanguage",input.inputLanguage()==null?"en-IN":input.inputLanguage()).put("explanationLanguage",input.explanationLanguage()==null?"en-IN":input.explanationLanguage());var turns=body.putArray("turns");int id=1;
        for(String line:input.transcript().split("\\R")) {
            if(line.isBlank()) continue;
            String speaker="unknown",text=line.trim();
            if(text.toLowerCase(Locale.ROOT).startsWith("caller:")){speaker="caller";text=text.substring(7).trim();}
            else if(text.toLowerCase(Locale.ROOT).startsWith("customer:")){speaker="customer";text=text.substring(9).trim();}
            if(text.length()>1000) throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,"Keep each conversation line under 1000 characters.");
            turns.addObject().put("id","t"+id++).put("speaker",speaker).put("text",text);
        }
        JsonNode result=ai.request("POST","/api/v2/analyze/text",body);
        ((ObjectNode)result).put("originalTranscript",input.transcript()).put("inputLanguage",input.inputLanguage()==null?"en-IN":input.inputLanguage());
        return saved.view(saved.save(saved.owner(principal),"TEXT",result));
    }
    @PostMapping(value="/analyze/audio",consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
    Map<String,Object> audio(@RequestParam MultipartFile file,@RequestParam boolean consent,@RequestParam(defaultValue="en-IN") String inputLanguage,@RequestParam(defaultValue="en-IN") String explanationLanguage,Principal principal) throws Exception {
        if(!consent) throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,"Recording consent is required.");
        if(file.getSize()>15*1024*1024) throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE,"Clip is too large.");
        String mime=file.getContentType();
        if(!Set.of("audio/wav","audio/x-wav","audio/wave","audio/mpeg").contains(mime==null?"":mime)) throw new ResponseStatusException(HttpStatus.UNSUPPORTED_MEDIA_TYPE,"Use WAV or MP3 audio.");
        if(!Set.of("en-IN","hi-IN","bn-IN","te-IN","ta-IN","mr-IN","gu-IN","kn-IN","ml-IN","pa-IN").contains(inputLanguage)) throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,"Select a supported Prisma audio language.");
        if(!Set.of("en-IN","hi-IN","hi-Latn","bn-IN","te-IN","ta-IN","mr-IN","gu-IN","kn-IN","ml-IN","or-IN","pa-IN").contains(explanationLanguage))throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,"Select a supported explanation language.");
        String boundary="callshield"+UUID.randomUUID().toString().replace("-","");
        var stream=new ByteArrayOutputStream();
        stream.write(("--"+boundary+"\r\nContent-Disposition: form-data; name=\"explanationLanguage\"\r\n\r\n"+explanationLanguage+"\r\n").getBytes(StandardCharsets.UTF_8));
        stream.write(("--"+boundary+"\r\nContent-Disposition: form-data; name=\"consent\"\r\n\r\ntrue\r\n--"+boundary+"\r\nContent-Disposition: form-data; name=\"inputLanguage\"\r\n\r\n"+inputLanguage+"\r\n--"+boundary+"\r\nContent-Disposition: form-data; name=\"file\"; filename=\"clip"+(mime.equals("audio/mpeg")?".mp3":".wav")+"\"\r\nContent-Type: "+mime+"\r\n\r\n").getBytes(StandardCharsets.UTF_8));
        stream.write(file.getBytes());stream.write(("\r\n--"+boundary+"--\r\n").getBytes(StandardCharsets.UTF_8));
        JsonNode result=ai.parse(ai.exchange("POST","/api/v2/analyze/audio",stream.toByteArray(),"multipart/form-data; boundary="+boundary));
        return saved.view(saved.save(saved.owner(principal),"AUDIO",result));
    }
    @GetMapping("/records") List<Map<String,Object>> list(Principal principal) {
        return saved.records.findByOwnerIdOrderByCreatedAtDesc(saved.owner(principal),PageRequest.of(0,100)).stream().map(record->{
            JsonNode result=saved.payload(record), assessment=result.path("assessment");
            Map<String,Object> summary=new LinkedHashMap<>();summary.put("id",record.id);summary.put("kind",record.kind);summary.put("createdAt",record.createdAt.toString());
            summary.put("title",result.path("originalTranscript").asText(record.kind.equals("LIVE")?"Live conversation":"Conversation review").substring(0,Math.min(90,result.path("originalTranscript").asText(record.kind.equals("LIVE")?"Live conversation":"Conversation review").length())));
            summary.put("score",assessment.has("score")?assessment.get("score"):null);summary.put("band",assessment.path("band").asText("UNDETERMINED"));summary.put("mock",result.path("mock").asBoolean());return summary;
        }).toList();
    }
    @GetMapping("/records/{id}") Map<String,Object> get(@PathVariable String id,Principal p){return saved.view(saved.owned(id,saved.owner(p)));}
    @DeleteMapping("/records/{id}") @ResponseStatus(HttpStatus.NO_CONTENT) void delete(@PathVariable String id,Principal p){var record=saved.owned(id,saved.owner(p));if(live.active(id))throw new ResponseStatusException(HttpStatus.CONFLICT,"Finish the live session before deleting its report.");saved.records.delete(record);}
    @PostMapping("/records/{id}/warning-audio") ResponseEntity<byte[]> warning(@PathVariable String id,@Valid @RequestBody WarningInput input,Principal p) {
        JsonNode result=saved.payload(saved.owned(id,saved.owner(p)));
        JsonNode score=result.path("assessment").path("score");
        if(!score.isInt()) throw new ResponseStatusException(HttpStatus.CONFLICT,"No current risk result is available.");
        if(score.asInt()<20) throw new ResponseStatusException(HttpStatus.CONFLICT,"Warning audio is not offered for minimal risk.");
        var body=json.createObjectNode().put("level",score.asInt()>=60?"HIGH_RISK":"SUSPICIOUS").put("language",input.language()==null?"en-IN":input.language());
        var response=ai.exchange("POST","/api/v2/warnings/synthesize",body.toString().getBytes(StandardCharsets.UTF_8),"application/json");
        return ResponseEntity.ok().contentType(MediaType.parseMediaType("audio/wav")).cacheControl(CacheControl.noStore()).header("X-Mock",response.headers().firstValue("X-Mock").orElse("false")).body(response.body());
    }
}

