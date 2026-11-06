package in.callshield.gateway;
import com.fasterxml.jackson.databind.*;
import java.net.*;
import java.net.http.*;
import java.time.Duration;
import java.nio.charset.StandardCharsets;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
@Service
public class AiClient {
    final String base,key;
    final HttpClient http=HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(5)).build();
    final ObjectMapper json;
    public AiClient(@Value("${callshield.ai-url}") String base,@Value("${callshield.ai-key}") String key,ObjectMapper json) {
        this.base=base.replaceAll("/$",""); this.key=key;this.json=json;
    }
    public JsonNode request(String method,String path,JsonNode body) {return parse(exchange(method,path,body==null?null:body.toString().getBytes(StandardCharsets.UTF_8),"application/json"));}
    public HttpResponse<byte[]> exchange(String method,String path,byte[] body,String contentType) {
        try {
            var builder=HttpRequest.newBuilder(URI.create(base+path)).timeout(Duration.ofSeconds(330)).header("X-API-Key",key);
            if(body!=null) builder.header("Content-Type",contentType);
            var response=http.send(builder.method(method,body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofByteArray(body)).build(),HttpResponse.BodyHandlers.ofByteArray());
            if(response.statusCode()>=400) {
                String code="AI_UNAVAILABLE",message="The analysis service could not complete this request."; boolean retry=response.statusCode()>=500;
                try {var error=json.readTree(response.body()).path("error"); if(error.has("code")&&error.has("message")){code=error.path("code").asText();message=error.path("message").asText();retry=error.path("retryable").asBoolean();}} catch(Exception ignored) {}
                throw new AiFailure(response.statusCode(),code,message,retry);
            }
            return response;
        } catch(AiFailure e) {throw e;} catch(HttpTimeoutException e) {throw new AiFailure(504,"TIMEOUT","The analysis service timed out.",true);}
        catch(InterruptedException e) {Thread.currentThread().interrupt();throw new AiFailure(503,"AI_UNAVAILABLE","Analysis interrupted.",true);}
        catch(Exception e) {throw new AiFailure(503,"AI_UNAVAILABLE","The analysis service is offline. Check the private connection.",true);}
    }
    JsonNode parse(HttpResponse<byte[]> response) {try{return json.readTree(response.body());}catch(Exception e){throw new AiFailure(502,"INVALID_RESPONSE","The analysis service returned an invalid response.",false);}}
    public URI socketUri(String sessionId) {return URI.create(base.replaceFirst("^http","ws")+"/api/v2/sessions/"+sessionId+"/stream");}
    static class AiFailure extends RuntimeException {
        final int status; final String code; final boolean retryable;
        AiFailure(int status,String code,String message,boolean retryable) {super(message);this.status=status;this.code=code;this.retryable=retryable;}
    }
}
