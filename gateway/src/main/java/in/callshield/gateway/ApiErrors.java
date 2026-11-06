package in.callshield.gateway;
import java.util.Map;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.dao.DataIntegrityViolationException;
@RestControllerAdvice
public class ApiErrors {
    private ResponseEntity<?> error(int status,String code,String message,boolean retry) {return ResponseEntity.status(status).body(Map.of("error",Map.of("code",code,"message",message,"retryable",retry)));}
    @ExceptionHandler(AiClient.AiFailure.class) ResponseEntity<?> ai(AiClient.AiFailure e) {return error(e.status,e.code,e.getMessage(),e.retryable);}
    @ExceptionHandler(ResponseStatusException.class) ResponseEntity<?> status(ResponseStatusException e) {return error(e.getStatusCode().value(),"REQUEST_REJECTED",e.getReason()==null?"Request rejected.":e.getReason(),false);}
    @ExceptionHandler(AuthenticationException.class) ResponseEntity<?> auth() {return error(401,"INVALID_CREDENTIALS","Email or password is incorrect.",false);}
    @ExceptionHandler(MethodArgumentNotValidException.class) ResponseEntity<?> validation() {return error(422,"INVALID_INPUT","Check your input. Passwords need at least 12 characters; conversation turns at most 1000 characters.",false);}
    @ExceptionHandler(MaxUploadSizeExceededException.class) ResponseEntity<?> size() {return error(413,"UPLOAD_TOO_LARGE","Choose a recording smaller than 15 MiB.",false);}
    @ExceptionHandler(DataIntegrityViolationException.class) ResponseEntity<?> conflict() {return error(409,"CONFLICT","This record already exists.",false);}
    @ExceptionHandler(Exception.class) ResponseEntity<?> unexpected() {return error(500,"INTERNAL_ERROR","Something went wrong. Please try again.",false);}
}
