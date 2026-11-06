package in.callshield.gateway;
import jakarta.servlet.http.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.security.authentication.*;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.csrf.CsrfToken;
@RestController @RequestMapping("/api/auth")
public class AuthController {
    record Registration(@Email @NotBlank @Size(max=255) String email,@NotBlank @Size(min=2,max=80) String name,@NotBlank @Size(min=12,max=72) String password) {}
    record Login(@NotBlank @Size(max=255) String email,@NotBlank @Size(max=128) String password) {}
    private final AccountRepository accounts; private final PasswordEncoder encoder; private final AuthenticationManager manager; private final HttpSessionSecurityContextRepository contexts;
    public AuthController(AccountRepository a,PasswordEncoder e,AuthenticationManager m,HttpSessionSecurityContextRepository c) {accounts=a;encoder=e;manager=m;contexts=c;}
    @GetMapping("/csrf") Map<String,String> csrf(CsrfToken token) {return Map.of("token",token.getToken(),"headerName",token.getHeaderName());}
    @PostMapping("/register") @ResponseStatus(HttpStatus.CREATED)
    Map<String,String> register(@Valid @RequestBody Registration input,HttpServletRequest req,HttpServletResponse res) {
        String email=input.email().trim().toLowerCase(Locale.ROOT);
        if(input.password().getBytes(StandardCharsets.UTF_8).length>72) throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Password must fit 72 UTF-8 bytes.");
        if(accounts.existsByEmail(email)) throw new ResponseStatusException(HttpStatus.CONFLICT,"Account already exists. Sign in instead.");
        accounts.saveAndFlush(new Account(email,input.name().trim(),encoder.encode(input.password())));
        return authenticate(email,input.password(),req,res);
    }
    @PostMapping("/login") Map<String,String> login(@Valid @RequestBody Login input,HttpServletRequest req,HttpServletResponse res) {return authenticate(input.email().trim().toLowerCase(Locale.ROOT),input.password(),req,res);}
    private Map<String,String> authenticate(String email,String password,HttpServletRequest req,HttpServletResponse res) {
        var auth=manager.authenticate(UsernamePasswordAuthenticationToken.unauthenticated(email,password));
        if(req.getSession(false)!=null) req.changeSessionId();
        var context=SecurityContextHolder.createEmptyContext();context.setAuthentication(auth);SecurityContextHolder.setContext(context);contexts.saveContext(context,req,res);
        return view(accounts.findByEmail(auth.getName()).orElseThrow());
    }
    @GetMapping("/me") Map<String,String> me(java.security.Principal principal) {return view(accounts.findByEmail(principal.getName()).orElseThrow());}
    private Map<String,String> view(Account a) {return Map.of("id",a.id,"email",a.email,"name",a.displayName);}
}
