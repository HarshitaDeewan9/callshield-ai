package in.callshield.gateway;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.*;
import org.springframework.mock.web.MockHttpSession;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
@SpringBootTest(properties={"spring.datasource.url=jdbc:h2:mem:gatewaytests;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1","spring.datasource.username=sa","spring.datasource.password="})
@AutoConfigureMockMvc
class GatewaySecurityTest {
    @Autowired MockMvc mvc; @Autowired ObjectMapper json; @Autowired AccountRepository accounts; @Autowired RecordRepository records;
    @MockitoBean AiClient ai;
    @BeforeEach void clean(){records.deleteAll();accounts.deleteAll();}
    MockHttpSession register(String email) throws Exception {
        var result=mvc.perform(post("/api/auth/register").with(csrf()).contentType("application/json").content(json.writeValueAsString(java.util.Map.of("email",email,"name","Studio User","password","a-strong-test-password-2026"))))
            .andExpect(status().isCreated()).andExpect(jsonPath("$.email").value(email)).andReturn();
        return (MockHttpSession)result.getRequest().getSession(false);
    }
    @Test void unauthenticatedAndCsrfAreEnforced() throws Exception {
        mvc.perform(get("/api/records")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/auth/register").contentType("application/json").content("{}")) .andExpect(status().isForbidden());
        mvc.perform(get("/api/auth/csrf")).andExpect(status().isOk()).andExpect(jsonPath("$.token").isString());
    }
    @Test void accountSessionAndLogout() throws Exception {
        var session=register("first@example.test");
        mvc.perform(get("/api/auth/me").session(session)).andExpect(status().isOk()).andExpect(jsonPath("$.name").value("Studio User")).andExpect(jsonPath("$.passwordHash").doesNotExist());
        mvc.perform(post("/api/auth/logout").session(session).with(csrf())).andExpect(status().isNoContent());
        mvc.perform(get("/api/auth/me")).andExpect(status().isUnauthorized());
    }
    @Test void ownershipSurvivesPersistenceAndPreventsReadingAndDeleting() throws Exception {
        var first=register("owner@example.test");
        when(ai.request(eq("POST"),eq("/api/v2/analyze/text"),any())).thenReturn(json.readTree("{\"status\":\"COMPLETED\",\"mock\":true,\"assessment\":{\"score\":90,\"band\":\"CRITICAL\",\"mock\":true}}"));
        var response=mvc.perform(post("/api/analyze/text").session(first).with(csrf()).contentType("application/json").content("{\"transcript\":\"Caller: Tell me your OTP now.\",\"inputLanguage\":\"en-IN\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.result.assessment.score").value(90)).andReturn();
        String id=json.readTree(response.getResponse().getContentAsString()).path("id").asText();
        var second=register("other@example.test");
        mvc.perform(get("/api/records/"+id).session(second)).andExpect(status().isNotFound());
        mvc.perform(delete("/api/records/"+id).session(second).with(csrf())).andExpect(status().isNotFound());
        mvc.perform(get("/api/records").session(second)).andExpect(jsonPath("$.length()").value(0));
        mvc.perform(get("/api/records/"+id).session(first)).andExpect(status().isOk());
        mvc.perform(delete("/api/records/"+id).session(first).with(csrf())).andExpect(status().isNoContent());
    }
    @Test void incorrectPasswordAndShortPasswordAreRejected() throws Exception {
        register("login@example.test");
        mvc.perform(post("/api/auth/login").with(csrf()).contentType("application/json").content("{\"email\":\"login@example.test\",\"password\":\"incorrect\"}")) .andExpect(status().isUnauthorized());
        mvc.perform(post("/api/auth/register").with(csrf()).contentType("application/json").content("{\"email\":\"new@example.test\",\"name\":\"New User\",\"password\":\"short\"}")) .andExpect(status().isUnprocessableEntity());
    }
    @Test void warningUsesPersistedScoreNotClientText() throws Exception {
        var session=register("warning@example.test");var account=accounts.findByEmail("warning@example.test").orElseThrow();
        records.save(new AnalysisRecord("saved",account.id,"TEXT","{\"assessment\":{\"score\":10}}"));
        mvc.perform(post("/api/records/saved/warning-audio").session(session).with(csrf()).contentType("application/json").content("{\"language\":\"en-IN\"}")) .andExpect(status().isConflict());
        verify(ai,never()).exchange(anyString(),anyString(),any(),anyString());
    }
    @Test void nativeScriptAndExplanationLocaleReachPythonUnchanged() throws Exception {
        var session=register("multilingual@example.test");
        when(ai.request(eq("POST"),eq("/api/v2/analyze/text"),any())).thenReturn(json.readTree("{\"status\":\"COMPLETED\",\"mock\":true,\"assessment\":{\"score\":10}}"));
        var body=java.util.Map.of("transcript","உங்கள் OTP எண்ணை சொல்லுங்கள்.","inputLanguage","ta-IN","explanationLanguage","hi-IN");
        mvc.perform(post("/api/analyze/text").session(session).with(csrf()).contentType("application/json").content(json.writeValueAsString(body)))
            .andExpect(status().isOk()).andExpect(jsonPath("$.result.inputLanguage").value("ta-IN"));
        var captured=org.mockito.ArgumentCaptor.forClass(JsonNode.class);
        verify(ai).request(eq("POST"),eq("/api/v2/analyze/text"),captured.capture());
        org.junit.jupiter.api.Assertions.assertEquals("ta-IN",captured.getValue().path("inputLanguage").asText());
        org.junit.jupiter.api.Assertions.assertEquals("hi-IN",captured.getValue().path("explanationLanguage").asText());
        org.junit.jupiter.api.Assertions.assertEquals(body.get("transcript"),captured.getValue().path("turns").get(0).path("text").asText());
    }
}
