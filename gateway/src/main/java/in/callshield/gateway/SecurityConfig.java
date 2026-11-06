package in.callshield.gateway;
import org.springframework.context.annotation.*;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.csrf.*;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.core.userdetails.*;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
@Configuration
public class SecurityConfig {
    @Bean PasswordEncoder encoder() { return new BCryptPasswordEncoder(12); }
    @Bean UserDetailsService users(AccountRepository accounts) {
        return email -> {
            var account=accounts.findByEmail(email.toLowerCase(java.util.Locale.ROOT)).orElseThrow(()->new UsernameNotFoundException("Invalid credentials"));
            return User.withUsername(account.email).password(account.passwordHash).roles("USER").build();
        };
    }
    @Bean AuthenticationManager manager(AuthenticationConfiguration config) throws Exception { return config.getAuthenticationManager(); }
    @Bean HttpSessionSecurityContextRepository contextRepository() { return new HttpSessionSecurityContextRepository(); }
    @Bean SecurityFilterChain chain(HttpSecurity http,HttpSessionSecurityContextRepository repo) throws Exception {
        var csrf=CookieCsrfTokenRepository.withHttpOnlyFalse();
        return http.csrf(c->c.csrfTokenRepository(csrf).csrfTokenRequestHandler(new CsrfTokenRequestAttributeHandler()))
            .securityContext(c->c.securityContextRepository(repo))
            .authorizeHttpRequests(a->a.requestMatchers("/api/auth/csrf","/api/auth/register","/api/auth/login","/api/health").permitAll().anyRequest().authenticated())
            .exceptionHandling(e->e.authenticationEntryPoint((req,res,ex)->{res.setStatus(401);res.setContentType("application/json");res.getWriter().write("{\"error\":{\"code\":\"UNAUTHORIZED\",\"message\":\"Please sign in.\"}}");})
                .accessDeniedHandler((req,res,ex)->{res.setStatus(403);res.setContentType("application/json");res.getWriter().write("{\"error\":{\"code\":\"FORBIDDEN\",\"message\":\"Request denied. Refresh and try again.\"}}");}))
            .logout(l->l.logoutUrl("/api/auth/logout").invalidateHttpSession(true).deleteCookies("JSESSIONID").logoutSuccessHandler((req,res,auth)->res.setStatus(204)))
            .headers(h->h.cacheControl(c->{}))
            .build();
    }
}
