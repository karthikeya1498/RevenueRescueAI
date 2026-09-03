describe('RevenueRescue AI authentication', () => {
  beforeEach(() => {
    cy.visit('/');
  });

  it('renders the sign-in experience and enters the dashboard', () => {
    cy.contains('Recover revenue.').should('be.visible');
    cy.get('input[type="email"]').should('have.value', 'alex@northstar.io');
    cy.get('input[type="password"]').should('have.attr', 'type', 'password');
    cy.contains('Sign in to RevenueRescue').click();
    cy.contains('Good morning, Alex').should('be.visible');
    cy.contains('Revenue recovered').should('be.visible');
  });

  it('switches to registration mode and exposes the additional identity field', () => {
    cy.contains('Create account').first().click();
    cy.contains('Create your workspace').should('be.visible');
    cy.get('input[placeholder="Alex Morgan"]').should('be.visible');
    cy.contains('Create workspace').should('be.visible');
  });

  it('toggles password visibility', () => {
    cy.get('input[type="password"]').should('exist');
    cy.get('button[aria-label="Toggle password visibility"]').click();
    cy.get('input[type="text"]').should('have.value', 'password123');
  });
});

describe('RevenueRescue AI realtime dashboard', () => {
  beforeEach(() => {
    cy.visit('/');
    cy.contains('Sign in to RevenueRescue').click();
  });

  it('connects to the live recovery feed and shows an event alert', () => {
    cy.contains('Live', { timeout: 8000 }).should('be.visible');
    cy.contains('LIVE EVENT', { timeout: 15000 }).should('be.visible');
    cy.contains('Just now · live').should('be.visible');
  });

  it('stores incoming events in the live alerts notification center', () => {
    cy.contains('LIVE EVENT', { timeout: 15000 }).should('be.visible');
    cy.get('button[aria-label="Open live alerts"]').click();
    cy.contains('Live alerts').should('be.visible');
    cy.contains('Recovery events from your workspace').should('be.visible');
    cy.get('.notification-item').should('have.length.greaterThan', 0);
  });

  it('navigates across dashboard surfaces while the connection remains visible', () => {
    cy.contains('Recovery queue').first().click();
    cy.contains('Open opportunities').should('be.visible');
    cy.contains('Live', { timeout: 8000 }).should('be.visible');
    cy.contains('Playbooks').first().click();
    cy.contains('Automation studio').should('be.visible');
    cy.contains('Architecture').first().click();
    cy.contains('Hybrid recovery mesh').should('be.visible');
  });
});
