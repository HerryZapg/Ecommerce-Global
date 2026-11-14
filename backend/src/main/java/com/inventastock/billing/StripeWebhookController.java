package com.inventastock.billing;

import com.stripe.exception.SignatureVerificationException;
import com.stripe.model.Event;
import com.stripe.net.Webhook;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;
import java.io.IOException;
import java.util.stream.Collectors;

@RestController
public class StripeWebhookController {

  @Value("${stripe.webhook.secret:}")
  String webhookSecret;

  @Value("${stripe.api.key:}")
  String stripeApiKey;

  @PostMapping("/webhooks/stripe")
  public ResponseEntity<String> handleStripe(HttpServletRequest request) throws IOException {
    String payload = request.getReader().lines().collect(Collectors.joining());
    String sigHeader = request.getHeader("Stripe-Signature");

    try {
      Event event = Webhook.constructEvent(payload, sigHeader, webhookSecret);
      // TODO: handle event types (subscription created/updated/canceled)
      return ResponseEntity.ok("ok");
    } catch (SignatureVerificationException e) {
      return ResponseEntity.badRequest().body("invalid signature");
    }
  }
}

