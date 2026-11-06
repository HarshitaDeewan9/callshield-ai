package in.callshield.gateway;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
@Component
public class AuthRateLimit extends OncePerRequestFilter {
    record Window(long start,int count) {}
    final ConcurrentHashMap<String,Window> attempts=new ConcurrentHashMap<>();
    @Override protected void doFilterInternal(HttpServletRequest request,HttpServletResponse response,FilterChain chain) throws ServletException,IOException {
        if(request.getMethod().equals("POST")&&(request.getRequestURI().equals("/api/auth/login")||request.getRequestURI().equals("/api/auth/register"))){
            long now=System.currentTimeMillis();
            if(attempts.size()>10000)attempts.entrySet().removeIf(e->now-e.getValue().start()>60000);
            Window window=attempts.compute(request.getRemoteAddr(),(key,old)->old==null||now-old.start()>60000?new Window(now,1):new Window(old.start(),old.count()+1));
            if(window.count()>20){response.setStatus(429);response.setContentType("application/json");response.getWriter().write("{\"error\":{\"code\":\"RATE_LIMITED\",\"message\":\"Too many sign-in attempts. Wait one minute.\"}}");return;}
        }
        chain.doFilter(request,response);
    }
}
