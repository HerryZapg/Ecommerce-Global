describe("smoke", () => {
  it("loads admin home", () => {
    cy.visit("/admin");
    cy.contains("InventaStock");
  });
});

