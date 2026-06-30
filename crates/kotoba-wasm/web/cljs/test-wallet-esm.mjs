import {
  applyWalletCommands,
  createWalletProvider,
  runWalletEffect,
  walletRequest,
} from '../cljs-out/kotoba-node.js';

const account = {
  id: 'acct:main',
  address: '0xabc0000000000000000000000000000000000000',
  pkh: 'did:pkh:eip155:1:0xabc0000000000000000000000000000000000000',
};

const otherAccount = {
  id: 'acct:other',
  address: '0xbbb0000000000000000000000000000000000000',
  pkh: 'did:pkh:eip155:1:0xbbb0000000000000000000000000000000000000',
};

const state = {
  accounts: {
    'acct:main': account,
  },
  networks: {
    1: { chainId: 1, name: 'Ethereum Mainnet' },
  },
  policies: {
    'https://app.example': {
      origin: 'https://app.example',
      accounts: ['acct:main'],
      chains: [1],
      caps: ['eth/accounts', 'eth/chain-id', 'eth/add-chain', 'eth/watch-asset', 'eth/call', 'eth/send-tx'],
    },
  },
  assets: {},
  allowances: {},
  balances: {},
  intents: {},
  quotes: {},
  signatures: {},
  txs: {},
  selectedAccountId: 'acct:main',
  selectedChainId: 1,
};

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function expectProviderError(promise, code, message) {
  try {
    await promise;
  } catch (error) {
    assert(error.code === code, `${message}: expected code ${code}, got ${error.code}`);
    assert(error.data && error.data.code === code, `${message}: missing structured error data`);
    return error;
  }
  throw new Error(`${message}: request unexpectedly succeeded`);
}

function expectSyncProviderError(fn, code, message) {
  try {
    fn();
  } catch (error) {
    assert(error.code === code, `${message}: expected code ${code}, got ${error.code}`);
    assert(error.data && error.data.code === code, `${message}: missing structured error data`);
    return error;
  }
  throw new Error(`${message}: request unexpectedly succeeded`);
}

function expectRuntimeError(fn, message) {
  try {
    fn();
  } catch (error) {
    assert(error.data && error.data['error-kind'] === 'wallet-runtime',
      `${message}: missing structured runtime error data`);
    return error;
  }
  throw new Error(`${message}: runtime effect unexpectedly succeeded`);
}

async function expectRuntimeErrorAsync(promise, message) {
  try {
    await promise;
  } catch (error) {
    assert(error.data && error.data['error-kind'] === 'wallet-runtime',
      `${message}: missing structured runtime error data`);
    return error;
  }
  throw new Error(`${message}: runtime effect unexpectedly succeeded`);
}

for (const [name, value] of Object.entries({
  walletRequest,
  createWalletProvider,
  runWalletEffect,
  applyWalletCommands,
})) {
  assert(typeof value === 'function', `${name} export is not a function`);
}

const accounts = walletRequest(state, 'https://app.example', {
  method: 'eth_accounts',
  params: [],
});
assert(accounts.result[0] === account.address, 'walletRequest did not return the authorized account');

const directRpc = walletRequest(state, 'https://app.example', {
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
});
assert(directRpc.effects[0].effect === 'evm-rpc/call',
  'walletRequest lost namespaced provider effect string');

const directMalformedRequest = expectSyncProviderError(() => walletRequest(state, 'https://app.example', null),
  -32602, 'walletRequest null request should expose structured provider error');
assert(directMalformedRequest.data['error-kind'] === 'invalid-params',
  'walletRequest null request did not preserve invalid-params kind');
assert(directMalformedRequest.data.method === 'provider.request',
  'walletRequest null request did not preserve provider.request method boundary');
assert(directMalformedRequest.data.reason === 'invalid-request',
  'walletRequest null request did not preserve invalid-request reason');

const directMalformedRequestMethod = expectSyncProviderError(() => walletRequest(state, 'https://app.example', {
  method: 1,
  params: [],
}), -32602, 'walletRequest numeric method should expose structured provider error');
assert(directMalformedRequestMethod.data['error-kind'] === 'invalid-params',
  'walletRequest numeric method did not preserve invalid-params kind');
assert(directMalformedRequestMethod.data.method === 'provider.request',
  'walletRequest numeric method did not preserve provider.request method boundary');
assert(directMalformedRequestMethod.data.reason === 'invalid-method',
  'walletRequest numeric method did not preserve invalid-method reason');

const directMalformedRequestParams = expectSyncProviderError(() => walletRequest(state, 'https://app.example', {
  method: 'eth_chainId',
  params: 'not-params',
}), -32602, 'walletRequest string params should expose structured provider error');
assert(directMalformedRequestParams.data['error-kind'] === 'invalid-params',
  'walletRequest string params did not preserve invalid-params kind');
assert(directMalformedRequestParams.data.method === 'eth_chainId',
  'walletRequest string params did not preserve request method');
assert(directMalformedRequestParams.data.reason === 'invalid-request-params',
  'walletRequest string params did not preserve invalid-request-params reason');

const directMalformedOrigin = expectSyncProviderError(() => walletRequest(state, 1, {
  method: 'eth_chainId',
  params: [],
}), -32602, 'walletRequest numeric origin should expose structured provider error');
assert(directMalformedOrigin.data['error-kind'] === 'invalid-params',
  'walletRequest numeric origin did not preserve invalid-params kind');
assert(directMalformedOrigin.data.method === 'walletRequest',
  'walletRequest numeric origin did not preserve method');
assert(directMalformedOrigin.data.reason === 'invalid-origin',
  'walletRequest numeric origin did not preserve invalid-origin reason');

const directBlankOrigin = expectSyncProviderError(() => walletRequest(state, '   ', {
  method: 'eth_chainId',
  params: [],
}), -32602, 'walletRequest blank origin should expose structured provider error');
assert(directBlankOrigin.data['error-kind'] === 'invalid-params',
  'walletRequest blank origin did not preserve invalid-params kind');
assert(directBlankOrigin.data.method === 'walletRequest',
  'walletRequest blank origin did not preserve method');
assert(directBlankOrigin.data.reason === 'invalid-origin',
  'walletRequest blank origin did not preserve invalid-origin reason');

const directInvalid = expectSyncProviderError(() => walletRequest(state, 'https://app.example', {
  method: 'eth_call',
  params: [{
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
    chainId: '0x2105',
  }, 'latest'],
}), 4902, 'walletRequest unregistered chain should expose structured provider error');
assert(directInvalid.data['error-kind'] === 'unknown-chain',
  'walletRequest provider error did not preserve error kind');
assert(directInvalid.data['chain-id'] === 8453,
  'walletRequest provider error did not preserve chain id');

const directInvalidKebabChain = expectSyncProviderError(() => walletRequest(state, 'https://app.example', {
  method: 'eth_call',
  params: [{
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
    'chain-id': null,
  }, 'latest'],
}), -32602, 'walletRequest invalid kebab chain-id should expose structured provider error');
assert(directInvalidKebabChain.data.reason === 'invalid-chain-id',
  'walletRequest invalid kebab chain-id did not preserve reason');
assert(directInvalidKebabChain.data.method === 'eth_call',
  'walletRequest invalid kebab chain-id did not preserve method');

const malformedWalletRequestState = expectSyncProviderError(() => walletRequest(
  null,
  'https://app.example',
  { method: 'eth_chainId', params: [] },
), -32602, 'walletRequest null state should expose structured provider error');
assert(malformedWalletRequestState.data['error-kind'] === 'invalid-params',
  'walletRequest null state did not preserve invalid-params kind');
assert(malformedWalletRequestState.data.method === 'walletRequest.state',
  'walletRequest null state did not preserve state boundary method');
assert(malformedWalletRequestState.data.reason === 'invalid-state',
  'walletRequest null state did not preserve invalid-state reason');

const malformedSelectedChainState = {
  ...state,
  selectedChainId: null,
};
const malformedWalletRequestChainId = expectSyncProviderError(() => walletRequest(
  malformedSelectedChainState,
  'https://app.example',
  { method: 'eth_chainId', params: [] },
), -32602, 'walletRequest malformed selectedChainId should expose structured provider error');
assert(malformedWalletRequestChainId.data['error-kind'] === 'invalid-params',
  'malformed walletRequest selectedChainId did not preserve invalid-params kind');
assert(malformedWalletRequestChainId.data.method === 'eth_chainId',
  'malformed walletRequest selectedChainId did not preserve method');
assert(malformedWalletRequestChainId.data.reason === 'invalid-selected-chain-id',
  'malformed walletRequest selectedChainId did not preserve reason');
const malformedWalletRequestCall = expectSyncProviderError(() => walletRequest(
  malformedSelectedChainState,
  'https://app.example',
  {
    method: 'eth_call',
    params: [{
      from: account.address,
      to: '0xdef0000000000000000000000000000000000000',
      data: '0x',
    }, 'latest'],
  },
), -32602, 'walletRequest malformed selectedChainId fallback should expose structured provider error');
assert(malformedWalletRequestCall.data.reason === 'invalid-selected-chain-id',
  'malformed walletRequest selectedChainId fallback did not preserve reason');

const malformedSelectedAccountState = {
  ...state,
  selectedAccountId: null,
};
const malformedWalletRequestAccount = expectSyncProviderError(() => walletRequest(
  malformedSelectedAccountState,
  'https://app.example',
  {
    method: 'eth_call',
    params: [{
      to: '0xdef0000000000000000000000000000000000000',
      data: '0x',
    }, 'latest'],
  },
), -32602, 'walletRequest malformed selectedAccountId fallback should expose structured provider error');
assert(malformedWalletRequestAccount.data['error-kind'] === 'invalid-params',
  'malformed walletRequest selectedAccountId did not preserve invalid-params kind');
assert(malformedWalletRequestAccount.data.method === 'eth_call',
  'malformed walletRequest selectedAccountId did not preserve method');
assert(malformedWalletRequestAccount.data.reason === 'invalid-selected-account-id',
  'malformed walletRequest selectedAccountId did not preserve reason');

const malformedProviderEnv = expectSyncProviderError(() => createWalletProvider(null),
  -32602, 'createWalletProvider null env should throw structured provider error');
assert(malformedProviderEnv.data['error-kind'] === 'invalid-params',
  'createWalletProvider null env did not preserve invalid-params kind');
assert(malformedProviderEnv.data.method === 'createWalletProvider',
  'createWalletProvider null env did not preserve method');
assert(malformedProviderEnv.data.reason === 'invalid-env',
  'createWalletProvider null env did not preserve invalid-env reason');

const malformedProviderInitialState = expectSyncProviderError(() => createWalletProvider({
  state: null,
  origin: 'https://app.example',
}), -32602, 'createWalletProvider null state should throw structured provider error');
assert(malformedProviderInitialState.data['error-kind'] === 'invalid-params',
  'createWalletProvider null state did not preserve invalid-params kind');
assert(malformedProviderInitialState.data.method === 'createWalletProvider.state',
  'createWalletProvider null state did not preserve state boundary method');
assert(malformedProviderInitialState.data.reason === 'invalid-state',
  'createWalletProvider null state did not preserve invalid-state reason');

const malformedProviderAccounts = expectSyncProviderError(() => createWalletProvider({
  state: {
    ...state,
    accounts: 'not-accounts',
  },
  origin: 'https://app.example',
}), -32602, 'createWalletProvider malformed accounts should throw structured provider error');
assert(malformedProviderAccounts.data['error-kind'] === 'invalid-params',
  'createWalletProvider malformed accounts did not preserve invalid-params kind');
assert(malformedProviderAccounts.data.method === 'createWalletProvider.state',
  'createWalletProvider malformed accounts did not preserve state boundary method');
assert(malformedProviderAccounts.data.reason === 'invalid-accounts',
  'createWalletProvider malformed accounts did not preserve invalid-accounts reason');

const malformedProviderNetworks = expectSyncProviderError(() => createWalletProvider({
  state: {
    ...state,
    networks: ['not-networks'],
  },
  origin: 'https://app.example',
}), -32602, 'createWalletProvider malformed networks should throw structured provider error');
assert(malformedProviderNetworks.data['error-kind'] === 'invalid-params',
  'createWalletProvider malformed networks did not preserve invalid-params kind');
assert(malformedProviderNetworks.data.method === 'createWalletProvider.state',
  'createWalletProvider malformed networks did not preserve state boundary method');
assert(malformedProviderNetworks.data.reason === 'invalid-networks',
  'createWalletProvider malformed networks did not preserve invalid-networks reason');

const malformedProviderPolicies = expectSyncProviderError(() => createWalletProvider({
  state: {
    ...state,
    policies: 'not-policies',
  },
  origin: 'https://app.example',
}), -32602, 'createWalletProvider malformed policies should throw structured provider error');
assert(malformedProviderPolicies.data['error-kind'] === 'invalid-params',
  'createWalletProvider malformed policies did not preserve invalid-params kind');
assert(malformedProviderPolicies.data.method === 'createWalletProvider.state',
  'createWalletProvider malformed policies did not preserve state boundary method');
assert(malformedProviderPolicies.data.reason === 'invalid-policies',
  'createWalletProvider malformed policies did not preserve invalid-policies reason');

const malformedProviderIntents = expectSyncProviderError(() => createWalletProvider({
  state: {
    ...state,
    intents: ['not-intents'],
  },
  origin: 'https://app.example',
}), -32602, 'createWalletProvider malformed intents should throw structured provider error');
assert(malformedProviderIntents.data['error-kind'] === 'invalid-params',
  'createWalletProvider malformed intents did not preserve invalid-params kind');
assert(malformedProviderIntents.data.method === 'createWalletProvider.state',
  'createWalletProvider malformed intents did not preserve state boundary method');
assert(malformedProviderIntents.data.reason === 'invalid-intents',
  'createWalletProvider malformed intents did not preserve invalid-intents reason');

const malformedProviderBalances = expectSyncProviderError(() => createWalletProvider({
  state: {
    ...state,
    balances: 'not-balances',
  },
  origin: 'https://app.example',
}), -32602, 'createWalletProvider malformed balances should throw structured provider error');
assert(malformedProviderBalances.data['error-kind'] === 'invalid-params',
  'createWalletProvider malformed balances did not preserve invalid-params kind');
assert(malformedProviderBalances.data.method === 'createWalletProvider.state',
  'createWalletProvider malformed balances did not preserve state boundary method');
assert(malformedProviderBalances.data.reason === 'invalid-balances',
  'createWalletProvider malformed balances did not preserve invalid-balances reason');

const malformedProviderPolicyOrigin = expectSyncProviderError(() => createWalletProvider({
  state: {
    ...state,
    policies: {
      'https://app.example': {
        ...state.policies['https://app.example'],
        origin: '   ',
      },
    },
  },
  origin: 'https://app.example',
}), -32602, 'createWalletProvider blank policy origin should throw structured provider error');
assert(malformedProviderPolicyOrigin.data['error-kind'] === 'invalid-params',
  'createWalletProvider blank policy origin did not preserve invalid-params kind');
assert(malformedProviderPolicyOrigin.data.method === 'createWalletProvider.state',
  'createWalletProvider blank policy origin did not preserve state boundary method');
assert(malformedProviderPolicyOrigin.data.reason === 'invalid-policy-origin',
  'createWalletProvider blank policy origin did not preserve invalid-policy-origin reason');

const malformedProviderOrigin = expectSyncProviderError(() => createWalletProvider({
  state,
  origin: 1,
}), -32602, 'createWalletProvider numeric origin should throw structured provider error');
assert(malformedProviderOrigin.data['error-kind'] === 'invalid-params',
  'createWalletProvider numeric origin did not preserve invalid-params kind');
assert(malformedProviderOrigin.data.method === 'createWalletProvider',
  'createWalletProvider numeric origin did not preserve method');
assert(malformedProviderOrigin.data.reason === 'invalid-origin',
  'createWalletProvider numeric origin did not preserve invalid-origin reason');

const blankProviderOrigin = expectSyncProviderError(() => createWalletProvider({
  state,
  origin: '   ',
}), -32602, 'createWalletProvider blank origin should throw structured provider error');
assert(blankProviderOrigin.data['error-kind'] === 'invalid-params',
  'createWalletProvider blank origin did not preserve invalid-params kind');
assert(blankProviderOrigin.data.method === 'createWalletProvider',
  'createWalletProvider blank origin did not preserve method');
assert(blankProviderOrigin.data.reason === 'invalid-origin',
  'createWalletProvider blank origin did not preserve invalid-origin reason');

const missingProviderOrigin = expectSyncProviderError(() => createWalletProvider({
  state,
}), -32602, 'createWalletProvider missing origin should throw structured provider error in Node');
assert(missingProviderOrigin.data['error-kind'] === 'invalid-params',
  'createWalletProvider missing origin did not preserve invalid-params kind');
assert(missingProviderOrigin.data.method === 'createWalletProvider',
  'createWalletProvider missing origin did not preserve method');
assert(missingProviderOrigin.data.reason === 'invalid-origin',
  'createWalletProvider missing origin did not preserve invalid-origin reason');

const malformedProviderHandleEffects = expectSyncProviderError(() => createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects: 'not-a-function',
}), -32602, 'createWalletProvider malformed handleEffects should throw structured provider error');
assert(malformedProviderHandleEffects.data['error-kind'] === 'invalid-params',
  'createWalletProvider malformed handleEffects did not preserve invalid-params kind');
assert(malformedProviderHandleEffects.data.method === 'createWalletProvider',
  'createWalletProvider malformed handleEffects did not preserve method');
assert(malformedProviderHandleEffects.data.reason === 'invalid-handle-effects',
  'createWalletProvider malformed handleEffects did not preserve invalid-handle-effects reason');

const provider = createWalletProvider({
  state,
  origin: 'https://app.example',
});

const malformedProviderEvent = expectSyncProviderError(() => provider.on(1, () => {}),
  -32602, 'provider.on malformed event should throw structured provider error');
assert(malformedProviderEvent.data['error-kind'] === 'invalid-params',
  'provider.on malformed event did not preserve invalid-params kind');
assert(malformedProviderEvent.data.method === 'provider.on',
  'provider.on malformed event did not preserve method');
assert(malformedProviderEvent.data.reason === 'invalid-event',
  'provider.on malformed event did not preserve invalid-event reason');
assert(malformedProviderEvent.data.event === 1,
  'provider.on malformed event did not preserve event');

const blankProviderEvent = expectSyncProviderError(() => provider.on('   ', () => {}),
  -32602, 'provider.on blank event should throw structured provider error');
assert(blankProviderEvent.data['error-kind'] === 'invalid-params',
  'provider.on blank event did not preserve invalid-params kind');
assert(blankProviderEvent.data.method === 'provider.on',
  'provider.on blank event did not preserve method');
assert(blankProviderEvent.data.reason === 'invalid-event',
  'provider.on blank event did not preserve invalid-event reason');
assert(blankProviderEvent.data.event === '   ',
  'provider.on blank event did not preserve event');

const malformedProviderListener = expectSyncProviderError(() => provider.on('accountsChanged', 'not-a-function'),
  -32602, 'provider.on malformed listener should throw structured provider error');
assert(malformedProviderListener.data['error-kind'] === 'invalid-params',
  'provider.on malformed listener did not preserve invalid-params kind');
assert(malformedProviderListener.data.method === 'provider.on',
  'provider.on malformed listener did not preserve method');
assert(malformedProviderListener.data.reason === 'invalid-listener',
  'provider.on malformed listener did not preserve invalid-listener reason');
assert(malformedProviderListener.data.event === 'accountsChanged',
  'provider.on malformed listener did not preserve event');

const malformedRemoveListenerEvent = expectSyncProviderError(() => provider.removeListener(1, () => {}),
  -32602, 'provider.removeListener malformed event should throw structured provider error');
assert(malformedRemoveListenerEvent.data['error-kind'] === 'invalid-params',
  'provider.removeListener malformed event did not preserve invalid-params kind');
assert(malformedRemoveListenerEvent.data.method === 'provider.removeListener',
  'provider.removeListener malformed event did not preserve method');
assert(malformedRemoveListenerEvent.data.reason === 'invalid-event',
  'provider.removeListener malformed event did not preserve invalid-event reason');
assert(malformedRemoveListenerEvent.data.event === 1,
  'provider.removeListener malformed event did not preserve event');

const blankRemoveListenerEvent = expectSyncProviderError(() => provider.removeListener('   ', () => {}),
  -32602, 'provider.removeListener blank event should throw structured provider error');
assert(blankRemoveListenerEvent.data['error-kind'] === 'invalid-params',
  'provider.removeListener blank event did not preserve invalid-params kind');
assert(blankRemoveListenerEvent.data.method === 'provider.removeListener',
  'provider.removeListener blank event did not preserve method');
assert(blankRemoveListenerEvent.data.reason === 'invalid-event',
  'provider.removeListener blank event did not preserve invalid-event reason');
assert(blankRemoveListenerEvent.data.event === '   ',
  'provider.removeListener blank event did not preserve event');

const malformedRemoveListener = expectSyncProviderError(() => provider.removeListener('accountsChanged', 'not-a-function'),
  -32602, 'provider.removeListener malformed listener should throw structured provider error');
assert(malformedRemoveListener.data['error-kind'] === 'invalid-params',
  'provider.removeListener malformed listener did not preserve invalid-params kind');
assert(malformedRemoveListener.data.method === 'provider.removeListener',
  'provider.removeListener malformed listener did not preserve method');
assert(malformedRemoveListener.data.reason === 'invalid-listener',
  'provider.removeListener malformed listener did not preserve invalid-listener reason');
assert(malformedRemoveListener.data.event === 'accountsChanged',
  'provider.removeListener malformed listener did not preserve event');

const malformedProviderRequest = await expectProviderError(provider.request(null),
  -32602, 'provider.request null request should reject with structured provider error');
assert(malformedProviderRequest.data['error-kind'] === 'invalid-params',
  'provider.request null request did not preserve invalid-params kind');
assert(malformedProviderRequest.data.method === 'provider.request',
  'provider.request null request did not preserve method');
assert(malformedProviderRequest.data.reason === 'invalid-request',
  'provider.request null request did not preserve invalid-request reason');

const malformedProviderRequestMethod = await expectProviderError(provider.request({ method: 1, params: [] }),
  -32602, 'provider.request numeric method should reject with structured provider error');
assert(malformedProviderRequestMethod.data['error-kind'] === 'invalid-params',
  'provider.request numeric method did not preserve invalid-params kind');
assert(malformedProviderRequestMethod.data.method === 'provider.request',
  'provider.request numeric method did not preserve method boundary');
assert(malformedProviderRequestMethod.data.reason === 'invalid-method',
  'provider.request numeric method did not preserve invalid-method reason');
assert(malformedProviderRequestMethod.data.actual === 1,
  'provider.request numeric method did not preserve actual method value');

const malformedProviderRequestParams = await expectProviderError(provider.request({
  method: 'eth_chainId',
  params: 'not-params',
}), -32602, 'provider.request string params should reject with structured provider error');
assert(malformedProviderRequestParams.data['error-kind'] === 'invalid-params',
  'provider.request string params did not preserve invalid-params kind');
assert(malformedProviderRequestParams.data.method === 'eth_chainId',
  'provider.request string params did not preserve request method');
assert(malformedProviderRequestParams.data.reason === 'invalid-request-params',
  'provider.request string params did not preserve invalid-request-params reason');
assert(malformedProviderRequestParams.data.actual === 'not-params',
  'provider.request string params did not preserve actual params value');

const chainId = await provider.request({ method: 'eth_chainId', params: [] });
assert(chainId === '0x1', `unexpected chain id ${chainId}`);

const providerInvalidKebabChain = await expectProviderError(provider.request({
  method: 'eth_call',
  params: [{
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
    'chain-id': null,
  }, 'latest'],
}), -32602, 'provider invalid kebab chain-id should expose structured provider error');
assert(providerInvalidKebabChain.data.reason === 'invalid-chain-id',
  'provider invalid kebab chain-id did not preserve reason');
assert(providerInvalidKebabChain.data.method === 'eth_call',
  'provider invalid kebab chain-id did not preserve method');

const malformedSelectedChainProvider = createWalletProvider({
  state: malformedSelectedChainState,
  origin: 'https://app.example',
});
const malformedProviderChainId = await expectProviderError(
  malformedSelectedChainProvider.request({ method: 'eth_chainId', params: [] }),
  -32602,
  'provider malformed selectedChainId should expose structured provider error',
);
assert(malformedProviderChainId.data['error-kind'] === 'invalid-params',
  'malformed provider selectedChainId did not preserve invalid-params kind');
assert(malformedProviderChainId.data.method === 'eth_chainId',
  'malformed provider selectedChainId did not preserve method');
assert(malformedProviderChainId.data.reason === 'invalid-selected-chain-id',
  'malformed provider selectedChainId did not preserve reason');
const malformedProviderCall = await expectProviderError(
  malformedSelectedChainProvider.request({
    method: 'eth_call',
    params: [{
      from: account.address,
      to: '0xdef0000000000000000000000000000000000000',
      data: '0x',
    }, 'latest'],
  }),
  -32602,
  'provider malformed selectedChainId fallback should expose structured provider error',
);
assert(malformedProviderCall.data.reason === 'invalid-selected-chain-id',
  'malformed provider selectedChainId fallback did not preserve reason');

const malformedSelectedAccountProvider = createWalletProvider({
  state: malformedSelectedAccountState,
  origin: 'https://app.example',
});
const malformedProviderAccount = await expectProviderError(
  malformedSelectedAccountProvider.request({
    method: 'eth_call',
    params: [{
      to: '0xdef0000000000000000000000000000000000000',
      data: '0x',
    }, 'latest'],
  }),
  -32602,
  'provider malformed selectedAccountId fallback should expose structured provider error',
);
assert(malformedProviderAccount.data['error-kind'] === 'invalid-params',
  'malformed provider selectedAccountId did not preserve invalid-params kind');
assert(malformedProviderAccount.data.method === 'eth_call',
  'malformed provider selectedAccountId did not preserve method');
assert(malformedProviderAccount.data.reason === 'invalid-selected-account-id',
  'malformed provider selectedAccountId did not preserve reason');

const txResult = await provider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
});
assert(txResult === null, 'eth_sendTransaction should return null before host effects');
assert(Object.keys(provider.getState().intents).length === 1, 'provider state did not retain the created intent');

try {
  await provider.request({ method: 'eth_sendTransaction', params: [{}] });
  throw new Error('invalid params request unexpectedly succeeded');
} catch (error) {
  assert(error.code === -32602, `expected -32602 invalid params, got ${error.code}`);
}

const unknownChain = await expectProviderError(provider.request({
  method: 'eth_call',
  params: [{
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
    chainId: '0x2105',
  }, 'latest'],
}), 4902, 'unregistered chain should reject before host RPC');
assert(unknownChain.data['error-kind'] === 'unknown-chain',
  'unregistered chain error did not preserve error kind');
assert(unknownChain.data['chain-id'] === 8453,
  'unregistered chain error did not preserve chain id');

const unknownAccount = await expectProviderError(provider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: '0x9990000000000000000000000000000000000000',
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }],
}), 4100, 'unregistered account should reject before intent creation');
assert(unknownAccount.data.address === '0x9990000000000000000000000000000000000000',
  'unregistered account error did not preserve address');

const beforeBadAddChainNetworks = Object.keys(provider.getState().networks).length;
const badAddChain = await expectProviderError(provider.request({
  method: 'wallet_addEthereumChain',
  params: [{
    chainId: '0xzz',
    chainName: 'Broken',
    nativeCurrency: { symbol: 'ETH' },
    rpcUrls: ['https://broken.example'],
  }],
}), -32602, 'invalid add-chain payload should reject at JS provider boundary');
assert(badAddChain.data.reason === 'invalid-chain-id',
  'invalid add-chain error did not preserve reason');
assert(Object.keys(provider.getState().networks).length === beforeBadAddChainNetworks,
  'invalid add-chain payload mutated provider network state');

const missingRpcUrls = await expectProviderError(provider.request({
  method: 'wallet_addEthereumChain',
  params: [{
    chainId: '0x2105',
    chainName: 'Base',
    nativeCurrency: { symbol: 'ETH' },
  }],
}), -32602, 'missing add-chain rpcUrls should reject at JS provider boundary');
assert(missingRpcUrls.data.reason === 'invalid-rpc-urls',
  'missing add-chain rpcUrls error did not preserve reason');

const addedBase = await provider.request({
  method: 'wallet_addEthereumChain',
  params: [{
    chainId: '0x2105',
    chainName: 'Base',
    nativeCurrency: { symbol: 'ETH' },
    rpcUrls: ['https://base.example'],
  }],
});
assert(addedBase === null, 'wallet_addEthereumChain should return null on success');
assert(provider.getState().networks['8453'].name === 'Base',
  'valid add-chain payload did not add Base network to provider state');

const beforeBadWatchAssets = Object.keys(provider.getState().assets).length;
const badWatchAsset = await expectProviderError(provider.request({
  method: 'wallet_watchAsset',
  params: [{
    type: 'ERC20',
    options: {
      address: '0xUSDC',
      symbol: 'USDC',
      decimals: 6,
    },
  }],
}), -32602, 'invalid watch-asset payload should reject at JS provider boundary');
assert(badWatchAsset.data.reason === 'invalid-asset-address',
  'invalid watch-asset error did not preserve reason');
assert(Object.keys(provider.getState().assets).length === beforeBadWatchAssets,
  'invalid watch-asset payload mutated provider asset state');

let watchAssetHostCalls = 0;
const watchAssetProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    watchAssetHostCalls += 1;
    throw new Error('wallet_watchAsset should not call host effects');
  },
});
const watchedAsset = await watchAssetProvider.request({
  method: 'wallet_watchAsset',
  params: [{
    type: 'ERC20',
    options: {
      address: '0x0000000000000000000000000000000000000abc',
      symbol: 'USDC',
      decimals: 6,
    },
  }],
});
const watchedAssets = Object.values(watchAssetProvider.getState().assets);
assert(watchedAsset === true,
  'valid watch-asset payload did not return true');
assert(watchedAssets.length === 1 && watchedAssets[0].symbol === 'USDC',
  'valid watch-asset payload did not update provider asset state');
assert(watchAssetHostCalls === 0,
  'wallet_watchAsset called handleEffects despite having no host effects');

const invalidReplayNetwork = expectRuntimeError(() => applyWalletCommands(state, [[
  'wallet/add-network',
  {
    chainId: 0,
    name: 'Broken',
    nativeSymbol: 'ETH',
    rpcRef: 'provider:0',
  },
]]), 'invalid add-network replay should expose structured runtime error data');
assert(invalidReplayNetwork.data.kind === 'wallet.network/chain-id',
  'invalid add-network replay did not preserve result kind');
assert(invalidReplayNetwork.data.field === 'chain-id' &&
  invalidReplayNetwork.data.actual === 0,
  'invalid add-network replay did not preserve field/actual data');

const invalidReplayAsset = expectRuntimeError(() => applyWalletCommands(state, [[
  'wallet/watch-asset',
  {
    chainId: 1,
    kind: 'asset.kind/erc20',
    address: '0xUSDC',
    symbol: 'USDC',
    decimals: 6,
  },
]]), 'invalid watch-asset replay should expose structured runtime error data');
assert(invalidReplayAsset.data.kind === 'wallet.asset/address',
  'invalid watch-asset replay did not preserve result kind');
assert(invalidReplayAsset.data.field === 'address' &&
  invalidReplayAsset.data.actual === '0xUSDC',
  'invalid watch-asset replay did not preserve field/actual data');

const invalidReplayConnect = expectRuntimeError(() => applyWalletCommands(state, [[
  'wallet/connect',
  {
    account: {
      id: 'acct:bad',
      address: '0xAlice',
      pkh: 'did:pkh:eip155:1:0xAlice',
    },
    origin: 'https://app.example',
    chains: [1],
    requested: ['eth/accounts'],
  },
]]), 'invalid connect replay should expose structured runtime error data');
assert(invalidReplayConnect.data.kind === 'wallet.connect/account-address',
  'invalid connect replay did not preserve result kind');
assert(invalidReplayConnect.data.field === 'address' &&
  invalidReplayConnect.data.actual === '0xAlice',
  'invalid connect replay did not preserve field/actual data');

const invalidReplayTransfer = expectRuntimeError(() => applyWalletCommands(state, [[
  'wallet/prepare-transfer',
  {
    id: 'transfer:bad-js',
    origin: 'https://app.example',
    asset: 'native',
    to: '0xdef0000000000000000000000000000000000000',
    amount: '0x10',
  },
]]), 'invalid prepare-transfer replay should expose structured runtime error data');
assert(invalidReplayTransfer.data.kind === 'wallet.transfer/amount',
  'invalid prepare-transfer replay did not preserve result kind');
assert(invalidReplayTransfer.data.field === 'amount' &&
  invalidReplayTransfer.data.actual === '0x10',
  'invalid prepare-transfer replay did not preserve field/actual data');

const invalidReplaySignature = expectRuntimeError(() => applyWalletCommands(state, [[
  'wallet/prepare-signature',
  {
    id: 'sign:bad-js',
    kind: 'intent.kind/message-sign',
    origin: 'https://app.example',
    chainId: 1,
    address: '0xAlice',
    payload: '0x68656c6c6f',
  },
]]), 'invalid prepare-signature replay should expose structured runtime error data');
assert(invalidReplaySignature.data.kind === 'wallet.signature/address',
  'invalid prepare-signature replay did not preserve result kind');
assert(invalidReplaySignature.data.field === 'address' &&
  invalidReplaySignature.data.actual === '0xAlice',
  'invalid prepare-signature replay did not preserve field/actual data');

const invalidReplaySelectNetwork = expectRuntimeError(() => applyWalletCommands(state, [[
  'wallet/select-network',
  {
    chainId: 0,
  },
]]), 'invalid select-network replay should expose structured runtime error data');
assert(invalidReplaySelectNetwork.data.kind === 'wallet.select-network/chain-id',
  'invalid select-network replay did not preserve result kind');
assert(invalidReplaySelectNetwork.data.field === 'chain-id' &&
  invalidReplaySelectNetwork.data.actual === 0,
  'invalid select-network replay did not preserve field/actual data');

const eventState = {
  ...state,
  networks: {
    ...state.networks,
    8453: { chainId: 8453, name: 'Base' },
  },
  policies: {
    'https://app.example': {
      ...state.policies['https://app.example'],
      chains: [1, 8453],
      caps: ['eth/accounts', 'eth/chain-id', 'eth/switch-chain'],
    },
  },
};
const eventProvider = createWalletProvider({
  state: eventState,
  origin: 'https://app.example',
});
const accountEvents = [];
const chainEvents = [];
const removedChainEvents = [];
const accountListener = (payload) => accountEvents.push(payload);
const chainListener = (payload) => chainEvents.push(payload);
const removedChainListener = (payload) => removedChainEvents.push(payload);
eventProvider.removeListener('chainChanged', removedChainListener);
eventProvider.removeListener('disconnect', removedChainListener);
eventProvider.on('accountsChanged', accountListener);
eventProvider.on('accountsChanged', () => {
  throw new Error('listener failure should not reject provider request');
});
eventProvider.on('chainChanged', chainListener);
eventProvider.on('chainChanged', removedChainListener);
eventProvider.removeListener('chainChanged', removedChainListener);
eventProvider.removeListener('chainChanged', removedChainListener);
const requestedAccounts = await eventProvider.request({ method: 'eth_requestAccounts', params: [] });
assert(requestedAccounts[0] === account.address,
  'eth_requestAccounts did not return authorized account through provider');
assert(accountEvents.length === 1 && accountEvents[0][0] === account.address,
  'eth_requestAccounts did not emit accountsChanged with authorized account despite a throwing listener');
await eventProvider.request({
  method: 'wallet_switchEthereumChain',
  params: [{ chainId: '0x2105' }],
});
assert(chainEvents.length === 1 && chainEvents[0] === '0x2105',
  'wallet_switchEthereumChain did not emit chainChanged with hex chain id');
assert(removedChainEvents.length === 0,
  'removeListener did not suppress removed chainChanged listener');

const replaceProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
});
const replacedChains = [];
const replacedAccounts = [];
replaceProvider.on('chainChanged', (payload) => replacedChains.push(payload));
replaceProvider.on('accountsChanged', (payload) => replacedAccounts.push(payload));
replaceProvider.on('accountsChanged', () => {
  throw new Error('setState listener failure should stay isolated');
});
replaceProvider.setState({
  ...state,
  networks: {
    ...state.networks,
    8453: { chainId: 8453, name: 'Base' },
  },
  policies: {
    'https://app.example': {
      ...state.policies['https://app.example'],
      accounts: [],
      chains: [8453],
    },
  },
  selectedChainId: 8453,
});
assert(replacedChains.length === 1 && replacedChains[0] === '0x2105',
  'setState did not emit chainChanged for selected chain replacement');
assert(replacedAccounts.length === 1 && replacedAccounts[0].length === 0,
  'setState did not emit accountsChanged for authorized account replacement');
assert(replaceProvider.getState()['selected-chain-id'] === 8453,
  'setState did not normalize replacement selectedChainId');
assert(replaceProvider.getState().networks['8453'].name === 'Base',
  'setState did not normalize replacement network map');

const hexChainState = {
  ...state,
  networks: {
    '0x1': { chainId: '0x1', name: 'Ethereum Mainnet' },
    '0x2105': { chainId: '0x2105', name: 'Base' },
  },
  policies: {
    'https://app.example': {
      ...state.policies['https://app.example'],
      accounts: [account.address],
      chains: ['0x1', '0x2105'],
      caps: ['eth_accounts', 'eth_chainId', 'eth_call', 'eth_sendTransaction'],
    },
  },
  selectedAccountId: account.address,
  selectedChainId: '0x1',
};
const hexPolicyAccounts = walletRequest(hexChainState, 'https://app.example', {
  method: 'eth_accounts',
  params: [],
});
assert(hexPolicyAccounts.result[0] === account.address,
  'walletRequest did not normalize address policy accounts before eth_accounts');
const hexPolicyRequest = walletRequest(hexChainState, 'https://app.example', {
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
});
assert(hexPolicyRequest.effects[0]['chain-id'] === 1,
  'walletRequest did not normalize method-name caps and hex policy chains before authorization');
const kebabHexChainRequest = walletRequest(hexChainState, 'https://app.example', {
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
    'chain-id': '0x2105',
  }, 'latest'],
});
assert(kebabHexChainRequest.effects[0]['chain-id'] === 8453,
  'walletRequest did not normalize kebab chain-id before authorization');
const selectedAddressTx = walletRequest(hexChainState, 'https://app.example', {
  method: 'eth_sendTransaction',
  params: [{
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
});
assert(selectedAddressTx.state.intents[Object.keys(selectedAddressTx.state.intents)[0]]['account-id'] === 'acct:main',
  'walletRequest did not normalize address selectedAccountId before intent creation');
const explicitFromChainState = {
  ...state,
  accounts: {
    ...state.accounts,
    'acct:other': otherAccount,
  },
  networks: {
    ...state.networks,
    8453: { chainId: '0x2105', name: 'Base' },
  },
  policies: {
    'https://app.example': {
      ...state.policies['https://app.example'],
      accounts: ['acct:main', 'acct:other'],
      chains: [1, '0x2105'],
    },
  },
};
const explicitFromTx = walletRequest(explicitFromChainState, 'https://app.example', {
  method: 'eth_sendTransaction',
  params: [{
    from: otherAccount.address,
    chainId: '0x2105',
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
});
const explicitFromIntent = Object.values(explicitFromTx.state.intents)[0];
assert(explicitFromIntent['account-id'] === 'acct:other',
  'walletRequest did not materialize from address as the transaction account id');
assert(explicitFromIntent['chain-id'] === 8453,
  'walletRequest did not materialize transaction chainId before intent creation');
const accountIdAddressState = {
  ...state,
  policies: {
    'https://app.example': {
      ...state.policies['https://app.example'],
      caps: [...state.policies['https://app.example'].caps, 'wallet_prepareTransfer'],
    },
  },
};
const addressAccountTransfer = walletRequest(accountIdAddressState, 'https://app.example', {
  method: 'wallet_prepareTransfer',
  params: [{
    accountId: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    amount: '1000000',
  }],
});
assert(Object.values(addressAccountTransfer.state.intents).some((intent) => intent['account-id'] === 'acct:main'),
  'walletRequest did not normalize address accountId before transfer intent creation');
const explicitFromTransfer = walletRequest({
  ...explicitFromChainState,
  policies: {
    'https://app.example': {
      ...explicitFromChainState.policies['https://app.example'],
      caps: [...explicitFromChainState.policies['https://app.example'].caps, 'wallet_prepareTransfer'],
    },
  },
}, 'https://app.example', {
  method: 'wallet_prepareTransfer',
  params: [{
    from: otherAccount.address,
    chainId: '0x2105',
    to: '0xdef0000000000000000000000000000000000000',
    amount: '1000000',
  }],
});
const explicitFromTransferIntent = Object.values(explicitFromTransfer.state.intents)[0];
assert(explicitFromTransferIntent['account-id'] === 'acct:other',
  'walletRequest did not materialize transfer from address as the account id');
assert(explicitFromTransferIntent['chain-id'] === 8453,
  'walletRequest did not materialize transfer chainId before intent creation');
const hexChainProvider = createWalletProvider({
  state: hexChainState,
  origin: 'https://app.example',
});
assert(await hexChainProvider.request({ method: 'eth_chainId', params: [] }) === '0x1',
  'provider did not normalize hex selectedChainId on initialization');
const hexProviderAccounts = await hexChainProvider.request({ method: 'eth_accounts', params: [] });
assert(hexProviderAccounts[0] === account.address,
  'provider did not normalize address policy accounts before eth_accounts');
const hexPolicyCall = await hexChainProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
});
assert(hexPolicyCall === null,
  'provider did not normalize method-name caps and hex policy chains before RPC authorization');
const selectedAddressProviderTx = await hexChainProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
});
assert(selectedAddressProviderTx === null,
  'provider rejected address selectedAccountId before intent creation');
assert(Object.values(hexChainProvider.getState().intents).some((intent) => intent['account-id'] === 'acct:main'),
  'provider did not normalize address selectedAccountId before storing intent');
const explicitFromProvider = createWalletProvider({
  state: explicitFromChainState,
  origin: 'https://app.example',
});
await explicitFromProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: otherAccount.address,
    chainId: '0x2105',
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
});
const explicitFromProviderIntent = Object.values(explicitFromProvider.getState().intents)[0];
assert(explicitFromProviderIntent['account-id'] === 'acct:other',
  'provider did not store transaction intent under the explicit from account');
assert(explicitFromProviderIntent['chain-id'] === 8453,
  'provider did not store transaction intent under the explicit chainId');
const explicitSignProvider = createWalletProvider({
  state: {
    ...explicitFromChainState,
    selectedChainId: 1,
    policies: {
      'https://app.example': {
        ...explicitFromChainState.policies['https://app.example'],
        caps: ['eth_accounts', 'eth_chainId', 'personal_sign', 'eth_signTypedData_v4'],
      },
    },
  },
  origin: 'https://app.example',
});
const explicitPersonalSignId = await explicitSignProvider.request({
  method: 'personal_sign',
  params: ['0x68656c6c6f', otherAccount.address],
});
assert(explicitSignProvider.getState().intents[explicitPersonalSignId]['account-id'] === 'acct:other',
  'provider did not materialize personal_sign address as the account id');
const explicitTypedSignId = await explicitSignProvider.request({
  method: 'eth_signTypedData_v4',
  params: [otherAccount.address, {
    domain: { name: 'Kotoba', chainId: 1 },
    message: { contents: 'hello' },
  }],
});
assert(explicitSignProvider.getState().intents[explicitTypedSignId]['account-id'] === 'acct:other',
  'provider did not materialize typed-data address as the account id');
const addressAccountProvider = createWalletProvider({
  state: accountIdAddressState,
  origin: 'https://app.example',
});
const addressAccountTransferId = await addressAccountProvider.request({
  method: 'wallet_prepareTransfer',
  params: [{
    accountId: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    amount: '1000000',
  }],
});
assert(addressAccountProvider.getState().intents[addressAccountTransferId]['account-id'] === 'acct:main',
  'provider did not normalize address accountId before storing transfer intent');
hexChainProvider.setState({
  ...hexChainState,
  selectedChainId: '0x2105',
});
assert(hexChainProvider.getState()['selected-chain-id'] === 8453,
  'provider did not normalize hex selectedChainId on setState');
const malformedSetStateError = expectSyncProviderError(() => hexChainProvider.setState({
  ...hexChainState,
  selectedChainId: null,
}), -32602, 'malformed setState should throw structured provider error');
assert(malformedSetStateError.data['error-kind'] === 'invalid-params',
  'malformed setState error did not preserve invalid-params kind');
assert(malformedSetStateError.data.method === 'provider.setState',
  'malformed setState error did not preserve method');
assert(malformedSetStateError.data.reason === 'invalid-selected-chain-id',
  'malformed setState error did not preserve reason');
assert(hexChainProvider.getState()['selected-chain-id'] === 8453,
  'malformed setState committed invalid selected chain');
const nullSetStateError = expectSyncProviderError(() => hexChainProvider.setState(null),
  -32602, 'null setState should throw structured provider error');
assert(nullSetStateError.data['error-kind'] === 'invalid-params',
  'null setState error did not preserve invalid-params kind');
assert(nullSetStateError.data.method === 'provider.setState',
  'null setState error did not preserve method');
assert(nullSetStateError.data.reason === 'invalid-state',
  'null setState error did not preserve invalid-state reason');
assert(hexChainProvider.getState()['selected-chain-id'] === 8453,
  'null setState corrupted existing provider state');

const hostHandledEffects = [];
const effectProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects(result) {
    hostHandledEffects.push(result.effects[0].effect);
    return { result: '0x2a' };
  },
});
const hostHandledCall = await effectProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
});
assert(hostHandledCall === '0x2a',
  'handleEffects result override was not returned from provider request');
assert(hostHandledEffects[0] === 'evm-rpc/call',
  'handleEffects did not receive provider effect');
assert(effectProvider.getState()['selected-chain-id'] === 1,
  'handleEffects result-only response corrupted provider selected chain');
assert(effectProvider.getState().accounts['acct:main'].address === account.address,
  'handleEffects result-only response corrupted provider accounts');

const asyncHostHandledEffects = [];
const asyncEffectProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects(result) {
    asyncHostHandledEffects.push(result.effects[0].effect);
    return Promise.resolve({ result: '0x2c' });
  },
});
const asyncHostHandledCall = await asyncEffectProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
});
assert(asyncHostHandledCall === '0x2c',
  'async handleEffects result-only override was not returned from provider request');
assert(asyncHostHandledEffects[0] === 'evm-rpc/call',
  'async handleEffects did not receive provider effect');
assert(asyncEffectProvider.getState()['selected-chain-id'] === 1,
  'async handleEffects result-only response corrupted provider selected chain');
assert(asyncEffectProvider.getState().accounts['acct:main'].address === account.address,
  'async handleEffects result-only response corrupted provider accounts');

const malformedHostResultProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    return '0x2c';
  },
});
const malformedHostResultError = await expectProviderError(malformedHostResultProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
}), -32000, 'malformed handleEffects result should reject before state commit');
assert(malformedHostResultError.data['error-kind'] === 'host-effect',
  'malformed handleEffects result did not preserve host-effect kind');
assert(malformedHostResultError.data['host-error-data'].kind === 'wallet.host-result/malformed',
  'malformed handleEffects result did not preserve host error kind');
assert(malformedHostResultProvider.getState()['selected-chain-id'] === 1,
  'malformed handleEffects result corrupted provider selected chain');

const commandReplayProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    return {
      result: '0x2d',
      commands: [[
        'wallet/observe-balance',
        {
          accountId: 'acct:main',
          chainId: '0x1',
          asset: 'native',
          raw: '44',
          blockNumber: 23000005,
          observedAt: 1782560003000,
        },
      ], [
        'wallet/observe-allowance',
        {
          accountId: 'acct:main',
          chainId: '0x1',
          token: '0xusdc',
          spender: '0xrouter000000000000000000000000000000000000',
          amount: '2',
          blockNumber: 23000005,
          observedAt: 1782560003000,
        },
      ]],
    };
  },
});
const commandReplayResult = await commandReplayProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
});
assert(commandReplayResult === '0x2d',
  'provider host command replay changed request result');
assert(commandReplayProvider.getState().balances['["acct:main" 1 "native"]'].raw === '44',
  'provider host command replay did not materialize balance observation');
assert(commandReplayProvider.getState().allowances[
  '["acct:main" 1 "0xusdc" "0xrouter000000000000000000000000000000000000"]'
] === '2',
  'provider host command replay did not materialize allowance observation');

const commandReplayEventProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    return {
      result: '0x2f',
      commands: [[
        'wallet/connect',
        {
          account: otherAccount,
          origin: 'https://app.example',
          chains: [1],
          requested: ['eth/accounts', 'eth/call'],
        },
      ]],
    };
  },
});
const commandReplayAccountEvents = [];
commandReplayEventProvider.on('accountsChanged', (payload) => commandReplayAccountEvents.push(payload));
commandReplayEventProvider.on('accountsChanged', () => {
  throw new Error('command replay listener failure should not reject provider request');
});
const commandReplayEventResult = await commandReplayEventProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
});
assert(commandReplayEventResult === '0x2f',
  'provider host command replay event changed request result');
assert(commandReplayEventProvider.getState()['selected-account-id'] === otherAccount.id,
  'provider host command replay event did not commit selected account');
assert(commandReplayAccountEvents.length === 1 &&
  commandReplayAccountEvents[0][0] === otherAccount.address,
  'provider host command replay did not emit accountsChanged for replayed connect');

const commandReplayNoopEventProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    return {
      result: '0x30',
      commands: [[
        'wallet/connect',
        {
          account,
          origin: 'https://app.example',
          chains: [1],
          requested: ['eth/accounts', 'eth/call'],
        },
      ]],
    };
  },
});
const commandReplayNoopAccountEvents = [];
commandReplayNoopEventProvider.on('accountsChanged', (payload) => {
  commandReplayNoopAccountEvents.push(payload);
});
const commandReplayNoopEventResult = await commandReplayNoopEventProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
});
assert(commandReplayNoopEventResult === '0x30',
  'provider host command replay no-op event changed request result');
assert(commandReplayNoopAccountEvents.length === 0,
  'provider host command replay emitted duplicate accountsChanged for unchanged account');

const malformedCommandReplayProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    return {
      result: '0x2e',
      commands: [[
        'wallet/observe-balance',
        {
          accountId: 'acct:main',
          chainId: '0x1',
          asset: 'native',
          raw: '45',
          blockNumber: 23000006,
          observedAt: 1782560004000,
        },
      ], [
        'wallet/tx-confirmed',
        {
          hash: '0xmissingintent',
          intentId: 'intent:missing',
          blockNumber: 23000006,
        },
      ]],
    };
  },
});
const malformedCommandReplayError = await expectProviderError(malformedCommandReplayProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
}), -32000, 'malformed provider host command replay should reject before state commit');
assert(malformedCommandReplayError.data['error-kind'] === 'host-effect',
  'malformed provider host command replay did not preserve host-effect kind');
assert(malformedCommandReplayError.data.code === -32000,
  'malformed provider host command replay did not preserve structured error code');
assert(malformedCommandReplayError.data.method === 'eth_call' &&
  malformedCommandReplayError.data.origin === 'https://app.example',
  'malformed provider host command replay did not preserve method/origin');
assert(Object.keys(malformedCommandReplayProvider.getState().balances).length === 0,
  'malformed provider host command replay committed partial balance state');
assert(Object.keys(malformedCommandReplayProvider.getState().txs).length === 0,
  'malformed provider host command replay committed tx state');

const malformedCommandShapeProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    return {
      result: '0x2e',
      commands: [
        ['wallet/observe-balance'],
      ],
    };
  },
});
const malformedCommandShapeError = await expectProviderError(malformedCommandShapeProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
}), -32000, 'malformed provider host command tuple should reject before state commit');
assert(malformedCommandShapeError.data['error-kind'] === 'host-effect',
  'malformed provider host command tuple did not preserve host-effect kind');
assert(Object.keys(malformedCommandShapeProvider.getState().balances).length === 0,
  'malformed provider host command tuple committed partial balance state');

const malformedCommandBatchProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    return {
      result: '0x2e',
      commands: {
        bad: ['wallet/observe-balance', {}],
      },
    };
  },
});
const malformedCommandBatchError = await expectProviderError(malformedCommandBatchProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
}), -32000, 'malformed provider host command batch should reject before state commit');
assert(malformedCommandBatchError.data['error-kind'] === 'host-effect',
  'malformed provider host command batch did not preserve host-effect kind');
assert(malformedCommandBatchError.data['host-error-data'].kind === 'wallet.commands/malformed',
  'malformed provider host command batch did not preserve host error kind');
assert(Object.keys(malformedCommandBatchProvider.getState().balances).length === 0,
  'malformed provider host command batch committed partial balance state');

const nullCommandBatchProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    return {
      result: '0x2e',
      commands: null,
    };
  },
});
const nullCommandBatchError = await expectProviderError(nullCommandBatchProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
}), -32000, 'null provider host command batch should reject before state commit');
assert(nullCommandBatchError.data['error-kind'] === 'host-effect',
  'null provider host command batch did not preserve host-effect kind');
assert(nullCommandBatchError.data['host-error-data'].kind === 'wallet.commands/malformed',
  'null provider host command batch did not preserve host error kind');
assert(Object.keys(nullCommandBatchProvider.getState().balances).length === 0,
  'null provider host command batch committed partial balance state');

let unexpectedEffectFreeCalls = 0;
const effectFreeProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    unexpectedEffectFreeCalls += 1;
    throw new Error('effect-free request should not call host effects');
  },
});
const effectFreeAccountsEvents = [];
effectFreeProvider.on('accountsChanged', (payload) => effectFreeAccountsEvents.push(payload));
const effectFreeChainId = await effectFreeProvider.request({ method: 'eth_chainId', params: [] });
assert(effectFreeChainId === '0x1',
  'effect-free eth_chainId did not resolve without host effects');
const effectFreeAccounts = await effectFreeProvider.request({ method: 'eth_requestAccounts', params: [] });
assert(effectFreeAccounts[0] === account.address,
  'effect-free eth_requestAccounts did not resolve without host effects');
assert(effectFreeAccountsEvents.length === 1 && effectFreeAccountsEvents[0][0] === account.address,
  'effect-free eth_requestAccounts did not emit accountsChanged');
assert(unexpectedEffectFreeCalls === 0,
  'effect-free provider request called handleEffects');

const stateEchoEffects = [];
const stateEchoProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects(result) {
    const effect = result.effects[0].effect;
    stateEchoEffects.push(effect);
    return {
      ...result,
      result: effect === 'evm-rpc/call' ? '0x2b' : result.result,
    };
  },
});
const stateEchoCall = await stateEchoProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
});
assert(stateEchoCall === '0x2b',
  'handleEffects full-result echo did not return result override');
assert(stateEchoEffects[0] === 'evm-rpc/call',
  'handleEffects received denormalized provider RPC effect before echo');
const stateEchoTx = await stateEchoProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
});
assert(stateEchoTx === null,
  'handleEffects full-result echo changed eth_sendTransaction result');
assert(stateEchoEffects[1] === 'evm/simulate',
  'handleEffects received denormalized provider simulation effect before echo');
assert(stateEchoProvider.getState().intents[Object.keys(stateEchoProvider.getState().intents)[0]].status === 'intent.status/pending-user',
  'handleEffects full-result echo corrupted namespaced intent status');

const asyncStateEchoEffects = [];
const asyncStateEchoChains = [];
const asyncStateEchoProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects(result) {
    asyncStateEchoEffects.push(result.effects[0].effect);
    return Promise.resolve({
      ...result,
      state: {
        ...result.state,
        networks: {
          ...result.state.networks,
          8453: { chainId: '0x2105', name: 'Base' },
        },
        'selected-chain-id': '0x2105',
      },
    });
  },
});
asyncStateEchoProvider.on('chainChanged', (payload) => asyncStateEchoChains.push(payload));
const asyncStateEchoTx = await asyncStateEchoProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
});
assert(asyncStateEchoTx === null,
  'async handleEffects full-result echo changed eth_sendTransaction result');
assert(asyncStateEchoEffects[0] === 'evm/simulate',
  'async handleEffects received denormalized provider simulation effect before echo');
assert(asyncStateEchoProvider.getState()['selected-chain-id'] === 8453,
  'async handleEffects full-result echo did not commit normalized host state');
assert(asyncStateEchoChains[0] === '0x2105',
  'async handleEffects full-result echo did not emit normalized chainChanged');
assert(asyncStateEchoProvider.getState().intents[
  Object.keys(asyncStateEchoProvider.getState().intents)[0]
].status === 'intent.status/pending-user',
  'async handleEffects full-result echo corrupted namespaced intent status');

const malformedHostStateProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects(result) {
    return {
      ...result,
      state: {
        ...result.state,
        'selected-chain-id': null,
      },
    };
  },
});
const malformedHostStateError = await expectProviderError(malformedHostStateProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
}), -32000, 'malformed host state should reject before provider state commit');
assert(malformedHostStateError.data['error-kind'] === 'host-effect',
  'malformed host state error did not preserve host-effect kind');
assert(malformedHostStateError.data['host-error-data'].reason === 'invalid-selected-chain-id',
  'malformed host state error did not preserve host invalid selected-chain reason');
assert(malformedHostStateProvider.getState()['selected-chain-id'] === 1,
  'malformed host state corrupted provider selected chain');
assert(Object.keys(malformedHostStateProvider.getState().intents).length === 0,
  'malformed host state committed pending intent');

const nullHostStateProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects(result) {
    return {
      ...result,
      state: null,
    };
  },
});
const nullHostStateError = await expectProviderError(nullHostStateProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
}), -32000, 'null host state should reject before provider state commit');
assert(nullHostStateError.data['error-kind'] === 'host-effect',
  'null host state error did not preserve host-effect kind');
assert(nullHostStateError.data['host-error-data'].kind === 'wallet.host-state/malformed',
  'null host state error did not preserve host state malformed kind');
assert(nullHostStateProvider.getState()['selected-chain-id'] === 1,
  'null host state corrupted provider selected chain');
assert(Object.keys(nullHostStateProvider.getState().intents).length === 0,
  'null host state committed pending intent');

const asyncMalformedHostStateProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects(result) {
    return Promise.resolve({
      ...result,
      state: {
        ...result.state,
        'selected-chain-id': null,
      },
    });
  },
});
const asyncMalformedHostStateError = await expectProviderError(asyncMalformedHostStateProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
}), -32000, 'async malformed host state should reject before provider state commit');
assert(asyncMalformedHostStateError.data['error-kind'] === 'host-effect',
  'async malformed host state error did not preserve host-effect kind');
assert(asyncMalformedHostStateProvider.getState()['selected-chain-id'] === 1,
  'async malformed host state corrupted provider selected chain');
assert(Object.keys(asyncMalformedHostStateProvider.getState().intents).length === 0,
  'async malformed host state committed pending intent');

const throwingHostProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    throw new Error('host rpc unavailable');
  },
});
const throwingHostError = await expectProviderError(throwingHostProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
}), -32000, 'throwing handleEffects should reject with structured host error');
assert(throwingHostError.data['error-kind'] === 'host-effect',
  'throwing handleEffects error did not preserve host-effect kind');
assert(throwingHostError.data.method === 'eth_call',
  'throwing handleEffects error did not preserve provider method');
assert(throwingHostError.data.message === 'host rpc unavailable',
  'throwing handleEffects error did not preserve host message');
assert(Object.keys(throwingHostProvider.getState().intents).length === 0,
  'throwing handleEffects error mutated provider state');

const throwingTxHostProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    throw new Error('host tx unavailable');
  },
});
const throwingTxHostError = await expectProviderError(throwingTxHostProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
}), -32000, 'throwing tx handleEffects should reject before provider state commit');
assert(throwingTxHostError.data['error-kind'] === 'host-effect',
  'throwing tx handleEffects error did not preserve host-effect kind');
assert(throwingTxHostError.data.code === -32000,
  'throwing tx handleEffects error did not preserve structured error code');
assert(throwingTxHostError.data.message === 'host tx unavailable',
  'throwing tx handleEffects error did not preserve host message');
assert(throwingTxHostError.message === 'host tx unavailable',
  'throwing tx handleEffects error did not preserve JS error message');
assert(throwingTxHostError.data.method === 'eth_sendTransaction' &&
  throwingTxHostError.data.origin === 'https://app.example',
  'throwing tx handleEffects error did not preserve method/origin');
assert(Object.keys(throwingTxHostProvider.getState().intents).length === 0,
  'throwing tx handleEffects error committed pending intent');

const rejectingHostProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    return Promise.reject(new Error('host rejected'));
  },
});
const rejectingHostError = await expectProviderError(rejectingHostProvider.request({
  method: 'eth_call',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    data: '0x',
  }, 'latest'],
}), -32000, 'rejecting handleEffects should reject with structured host error');
assert(rejectingHostError.data['error-kind'] === 'host-effect',
  'rejecting handleEffects error did not preserve host-effect kind');
assert(rejectingHostError.data.message === 'host rejected',
  'rejecting handleEffects error did not preserve host message');

const rejectingTxHostProvider = createWalletProvider({
  state,
  origin: 'https://app.example',
  handleEffects() {
    return Promise.reject(new Error('host tx rejected'));
  },
});
const rejectingTxHostError = await expectProviderError(rejectingTxHostProvider.request({
  method: 'eth_sendTransaction',
  params: [{
    from: account.address,
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  }],
}), -32000, 'rejecting tx handleEffects should reject before provider state commit');
assert(rejectingTxHostError.data['error-kind'] === 'host-effect',
  'rejecting tx handleEffects error did not preserve host-effect kind');
assert(rejectingTxHostError.data.code === -32000,
  'rejecting tx handleEffects error did not preserve structured error code');
assert(rejectingTxHostError.data.message === 'host tx rejected',
  'rejecting tx handleEffects error did not preserve host message');
assert(rejectingTxHostError.message === 'host tx rejected',
  'rejecting tx handleEffects error did not preserve JS error message');
assert(rejectingTxHostError.data.method === 'eth_sendTransaction' &&
  rejectingTxHostError.data.origin === 'https://app.example',
  'rejecting tx handleEffects error did not preserve method/origin');
assert(Object.keys(rejectingTxHostProvider.getState().intents).length === 0,
  'rejecting tx handleEffects error committed pending intent');

const rpcRequests = [];
const rpc = runWalletEffect({
  evmRpcFn(request) {
    rpcRequests.push(request);
    return '0x2a';
  },
}, {
  effect: 'evm-rpc/call',
  chainId: '0x1',
  params: [{ to: '0xdef0000000000000000000000000000000000000', data: '0x' }, 'latest'],
});
assert(rpc.result === '0x2a', 'runWalletEffect did not return host RPC result');
assert(rpcRequests[0]['chain-id'] === 1, 'runWalletEffect did not normalize camelCase hex chainId effect keys');

const asyncRpcRequests = [];
const asyncRpc = await runWalletEffect({
  evmRpcFn(request) {
    asyncRpcRequests.push(request);
    return Promise.resolve({ value: '0x2b', chainId: '0x1' });
  },
}, {
  effect: 'evm-rpc/call',
  chainId: '0x1',
  params: [{ to: '0xdef0000000000000000000000000000000000000', data: '0x' }, 'latest'],
});
assert(asyncRpc.result.value === '0x2b',
  'runWalletEffect did not await async host RPC result');
assert(asyncRpc.result['chain-id'] === 1,
  'runWalletEffect did not normalize async host RPC result chainId');
assert(asyncRpcRequests[0]['chain-id'] === 1,
  'runWalletEffect did not normalize async host RPC request chainId');

const missingRuntimeCapability = expectRuntimeError(() => runWalletEffect({}, {
  effect: 'evm-rpc/call',
  chainId: 1,
  params: [{ to: '0xdef0000000000000000000000000000000000000', data: '0x' }, 'latest'],
}), 'missing runtime capability should expose structured error data');
assert(missingRuntimeCapability.data.capability === 'evm-rpc-fn',
  'missing runtime capability error did not preserve capability');

const malformedRuntimeCapability = expectRuntimeError(() => runWalletEffect({
  evmRpcFn: 'not-a-function',
}, {
  effect: 'evm-rpc/call',
  chainId: 1,
  params: [{ to: '0xdef0000000000000000000000000000000000000', data: '0x' }, 'latest'],
}), 'malformed runtime capability should expose structured error data');
assert(malformedRuntimeCapability.data.kind === 'wallet.capability/malformed',
  'malformed runtime capability did not preserve result kind');
assert(malformedRuntimeCapability.data.capability === 'evm-rpc-fn',
  'malformed runtime capability did not preserve capability');

const malformedRuntimeClockCapability = expectRuntimeError(() => runWalletEffect({
  clockFn: 'not-a-function',
  signFn(intent) {
    return {
      raw: '0xsigned',
      intentHash: intent.hash,
    };
  },
  submitRawTxFn(signedTx) {
    return {
      hash: '0xtxhash',
      raw: signedTx.raw,
    };
  },
}, {
  effect: 'wallet/sign-and-submit',
  intent: {
    id: 'intent:malformed-clock',
    status: 'intent.status/approved',
    accountId: 'acct:main',
    chainId: 1,
    origin: 'https://app.example',
    kind: 'intent.kind/contract-call',
    hash: 'wallet-intent:v1:malformed-clock',
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  },
}), 'malformed runtime clock capability should expose structured runtime error data');
assert(malformedRuntimeClockCapability.data.kind === 'wallet.capability/malformed',
  'malformed runtime clock capability did not preserve result kind');
assert(malformedRuntimeClockCapability.data.capability === 'clockFn',
  'malformed runtime clock capability did not preserve capability');
assert(malformedRuntimeClockCapability.data.actual === 'not-a-function',
  'malformed runtime clock capability did not preserve actual capability');

const malformedRuntimeEnv = expectRuntimeError(() => runWalletEffect(null, {
  effect: 'evm-rpc/call',
  chainId: 1,
  params: [{ to: '0xdef0000000000000000000000000000000000000', data: '0x' }, 'latest'],
}), 'malformed runtime env should expose structured runtime error data');
assert(malformedRuntimeEnv.data.kind === 'wallet.env/malformed',
  'malformed runtime env did not preserve result kind');
assert(malformedRuntimeEnv.data.actual === null,
  'malformed runtime env did not preserve actual env');

const malformedRuntimeEffect = expectRuntimeError(() => runWalletEffect({}, null),
  'malformed runtime effect should expose structured runtime error data');
assert(malformedRuntimeEffect.data.kind === 'wallet.effect/malformed',
  'malformed runtime effect did not preserve result kind');
assert(malformedRuntimeEffect.data.actual === null,
  'malformed runtime effect did not preserve actual effect');

const malformedRuntimeSignResult = expectRuntimeError(() => runWalletEffect({
  signFn() {
    return 'not-signed';
  },
  submitRawTxFn() {
    return {
      hash: '0xshouldnotsubmit',
    };
  },
}, {
  effect: 'wallet/sign-and-submit',
  intent: {
    id: 'intent:malformed-sign',
    status: 'intent.status/approved',
    accountId: 'acct:main',
    chainId: 1,
    origin: 'https://app.example',
    kind: 'intent.kind/contract-call',
    hash: 'wallet-intent:v1:malformed-sign',
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  },
}), 'malformed runtime sign result should expose structured runtime error data');
assert(malformedRuntimeSignResult.data.kind === 'wallet.sign/malformed',
  'malformed runtime sign result did not preserve result kind');
assert(malformedRuntimeSignResult.data.actual === 'not-signed',
  'malformed runtime sign result did not preserve actual result');

const asyncRuntimeError = await expectRuntimeErrorAsync(runWalletEffect({
  signMessageFn() {
    return Promise.reject(new Error('async signer unavailable'));
  },
}, {
  effect: 'wallet/sign-message',
  intent: {
    id: 'intent:async-sign',
    status: 'intent.status/approved',
    accountId: 'acct:main',
    chainId: 1,
    origin: 'https://app.example',
    kind: 'intent.kind/message-sign',
    payloadHash: 'payload:async',
  },
}), 'async host rejection should expose structured runtime error data');
assert(asyncRuntimeError.message === 'async signer unavailable',
  'async runtime error did not preserve host message');

const signed = runWalletEffect({
  clockFn() {
    return 1782560000700;
  },
  signMessageFn(intent) {
    return {
      signature: '0xsig',
      payloadHash: intent['payload-hash'],
    };
  },
}, {
  effect: 'wallet/sign-message',
  intent: {
    id: 'intent:sign',
    status: 'intent.status/approved',
    accountId: 'acct:main',
    chainId: 1,
    origin: 'https://app.example',
    kind: 'intent.kind/message-sign',
    payloadHash: 'payload:esm',
  },
});
assert(signed.commands[0][0] === 'wallet/message-signed', 'runWalletEffect lost command keyword namespace');

const applied = applyWalletCommands({
  ...state,
  intents: {
    'intent:sign': {
      id: 'intent:sign',
      status: 'intent.status/approved',
      payloadHash: 'payload:esm',
    },
  },
}, signed.commands);
assert(applied.state.intents['intent:sign'].status === 'intent.status/signed',
  'applyWalletCommands did not apply message-signed command');
assert(Object.keys(applied.state.signatures).length === 1,
  'applyWalletCommands did not retain signature fact');

const invalidReplay = expectRuntimeError(() => applyWalletCommands({
  ...state,
  intents: {},
}, [[
  'wallet/message-signed',
  {
    intentId: 'intent:missing',
    signature: '0xsig',
  },
]]), 'invalid command replay should expose structured runtime error data');
assert(invalidReplay.data.id === 'intent:missing',
  'invalid replay error did not preserve missing intent id');
assert(invalidReplay.data.observation === 'message/signed',
  'invalid replay error did not preserve observation kind');

const malformedRuntimeCommand = expectRuntimeError(() => applyWalletCommands(state, [
  ['wallet/observe-balance'],
]), 'malformed command tuple should expose structured runtime error data');
assert(malformedRuntimeCommand.data.kind === 'wallet.command/malformed',
  'malformed command tuple did not preserve result kind');
assert(Array.isArray(malformedRuntimeCommand.data.actual) &&
  malformedRuntimeCommand.data.actual.length === 1,
  'malformed command tuple did not preserve actual command shape');

const malformedRuntimeCommandBatch = expectRuntimeError(() => applyWalletCommands(state, {
  bad: ['wallet/observe-balance', {}],
}), 'malformed command batch should expose structured runtime error data');
assert(malformedRuntimeCommandBatch.data.kind === 'wallet.commands/malformed',
  'malformed command batch did not preserve result kind');
assert(malformedRuntimeCommandBatch.data.actual.bad[0] === 'wallet/observe-balance',
  'malformed command batch did not preserve actual command map');

const malformedRuntimeState = expectRuntimeError(() => applyWalletCommands(null, []),
  'malformed runtime state should expose structured runtime error data');
assert(malformedRuntimeState.data.kind === 'wallet.state/malformed',
  'malformed runtime state did not preserve result kind');
assert(malformedRuntimeState.data.actual === null,
  'malformed runtime state did not preserve actual state');

const malformedRuntimeAccounts = expectRuntimeError(() => applyWalletCommands({
  ...state,
  accounts: 'not-accounts',
}, []), 'malformed runtime accounts should expose structured runtime error data');
assert(malformedRuntimeAccounts.data.kind === 'wallet.accounts/malformed',
  'malformed runtime accounts did not preserve result kind');
assert(malformedRuntimeAccounts.data.actual === 'not-accounts',
  'malformed runtime accounts did not preserve actual accounts');

const malformedRuntimeNetworks = expectRuntimeError(() => applyWalletCommands({
  ...state,
  networks: ['not-networks'],
}, []), 'malformed runtime networks should expose structured runtime error data');
assert(malformedRuntimeNetworks.data.kind === 'wallet.networks/malformed',
  'malformed runtime networks did not preserve result kind');
assert(Array.isArray(malformedRuntimeNetworks.data.actual),
  'malformed runtime networks did not preserve actual networks');

const malformedRuntimePolicies = expectRuntimeError(() => applyWalletCommands({
  ...state,
  policies: 'not-policies',
}, []), 'malformed runtime policies should expose structured runtime error data');
assert(malformedRuntimePolicies.data.kind === 'wallet.policies/malformed',
  'malformed runtime policies did not preserve result kind');
assert(malformedRuntimePolicies.data.actual === 'not-policies',
  'malformed runtime policies did not preserve actual policies');

const malformedRuntimeIntents = expectRuntimeError(() => applyWalletCommands({
  ...state,
  intents: ['not-intents'],
}, []), 'malformed runtime intents should expose structured runtime error data');
assert(malformedRuntimeIntents.data.kind === 'wallet.intents/malformed',
  'malformed runtime intents did not preserve result kind');
assert(Array.isArray(malformedRuntimeIntents.data.actual),
  'malformed runtime intents did not preserve actual intents');

const malformedRuntimeBalances = expectRuntimeError(() => applyWalletCommands({
  ...state,
  balances: 'not-balances',
}, []), 'malformed runtime balances should expose structured runtime error data');
assert(malformedRuntimeBalances.data.kind === 'wallet.balances/malformed',
  'malformed runtime balances did not preserve result kind');
assert(malformedRuntimeBalances.data.actual === 'not-balances',
  'malformed runtime balances did not preserve actual balances');

const submitted = runWalletEffect({
  clockFn() {
    return 1782560000800;
  },
  signFn(intent) {
    return {
      raw: '0xsigned',
      nonce: 7,
      intentHash: intent.hash,
    };
  },
  submitRawTxFn(signedTx) {
    return {
      hash: '0xtxhash',
      raw: signedTx.raw,
    };
  },
}, {
  effect: 'wallet/sign-and-submit',
  intent: {
    id: 'intent:tx',
    status: 'intent.status/approved',
    accountId: 'acct:main',
    chainId: 1,
    origin: 'https://app.example',
    kind: 'intent.kind/contract-call',
    hash: 'wallet-intent:v1:esm',
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  },
});
assert(submitted.commands[0][0] === 'wallet/tx-signed',
  'sign-and-submit did not emit tx-signed command');
assert(submitted.commands[1][0] === 'wallet/tx-submitted',
  'sign-and-submit did not emit tx-submitted command');

const txApplied = applyWalletCommands({
  ...state,
  intents: {
    'intent:tx': {
      id: 'intent:tx',
      status: 'intent.status/approved',
    },
  },
}, submitted.commands);
assert(txApplied.state.intents['intent:tx'].status === 'intent.status/submitted',
  'applyWalletCommands did not submit signed transaction intent');
assert(txApplied.state.txs['0xtxhash'].hash === '0xtxhash',
  'applyWalletCommands did not retain tx hash');

const asyncSubmitted = await runWalletEffect({
  clockFn() {
    return 1782560000850;
  },
  signFn(intent) {
    return Promise.resolve({
      raw: '0xasyncsigned',
      nonce: 8,
      intentHash: intent.hash,
    });
  },
  submitRawTxFn(signedTx) {
    return Promise.resolve({
      hash: '0xasynctxhash',
      raw: signedTx.raw,
    });
  },
}, {
  effect: 'wallet/sign-and-submit',
  intent: {
    id: 'intent:async-tx',
    status: 'intent.status/approved',
    accountId: 'acct:main',
    chainId: 1,
    origin: 'https://app.example',
    kind: 'intent.kind/contract-call',
    hash: 'wallet-intent:v1:async-esm',
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  },
});
assert(asyncSubmitted.commands[0][0] === 'wallet/tx-signed' &&
  asyncSubmitted.commands[1][0] === 'wallet/tx-submitted',
  'async sign-and-submit did not emit signed/submitted commands');
assert(asyncSubmitted.commands[1][1].hash === '0xasynctxhash',
  'async sign-and-submit did not preserve submitted tx hash');

const runtimeHexSelected = applyWalletCommands(hexChainState, [[
  'wallet/prepare-contract-call',
  {
    id: 'intent:hex-chain',
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  },
]]);
assert(runtimeHexSelected.state.intents['intent:hex-chain']['chain-id'] === 1,
  'applyWalletCommands did not normalize hex selectedChainId before actor replay');
assert(runtimeHexSelected.state.intents['intent:hex-chain']['account-id'] === 'acct:main',
  'applyWalletCommands did not normalize address selectedAccountId before actor replay');
assert(runtimeHexSelected.state.policies['https://app.example'].accounts[0] === 'acct:main',
  'applyWalletCommands did not normalize address policy accounts before actor replay');
assert(runtimeHexSelected.state.policies['https://app.example'].caps.includes('eth/call'),
  'applyWalletCommands did not normalize method-name caps before actor replay');

const mismatchedSubmit = expectRuntimeError(() => runWalletEffect({
  signFn(intent) {
    return {
      raw: '0xsigned',
      intentHash: intent.hash,
    };
  },
  submitRawTxFn() {
    return {
      hash: '0xtxhash',
      raw: '0xdifferent',
    };
  },
}, {
  effect: 'wallet/sign-and-submit',
  intent: {
    id: 'intent:mismatch',
    status: 'intent.status/approved',
    accountId: 'acct:main',
    chainId: 1,
    origin: 'https://app.example',
    kind: 'intent.kind/contract-call',
    hash: 'wallet-intent:v1:mismatch',
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  },
}), 'mismatched submit raw should expose structured runtime error data');
assert(mismatchedSubmit.data.kind === 'wallet.submit/signed-raw',
  'mismatched submit error did not preserve mismatch kind');
assert(mismatchedSubmit.data.expected === '0xsigned' &&
  mismatchedSubmit.data.actual === '0xdifferent',
  'mismatched submit error did not preserve expected/actual raw transaction');

const invalidSubmitHash = expectRuntimeError(() => runWalletEffect({
  signFn(intent) {
    return {
      raw: '0xsigned',
      intentHash: intent.hash,
    };
  },
  submitRawTxFn(signedTx) {
    return {
      hash: 'submitted',
      raw: signedTx.raw,
    };
  },
}, {
  effect: 'wallet/sign-and-submit',
  intent: {
    id: 'intent:invalid-submit-hash',
    status: 'intent.status/approved',
    accountId: 'acct:main',
    chainId: 1,
    origin: 'https://app.example',
    kind: 'intent.kind/contract-call',
    hash: 'wallet-intent:v1:invalid-submit-hash',
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  },
}), 'invalid submit hash should expose structured runtime error data');
assert(invalidSubmitHash.data.kind === 'wallet.submit/hash',
  'invalid submit hash did not preserve result kind');
assert(invalidSubmitHash.data.field === 'hash' &&
  invalidSubmitHash.data.actual === 'submitted',
  'invalid submit hash did not preserve field/actual data');

const invalidSubmitClock = expectRuntimeError(() => runWalletEffect({
  clockFn() {
    return '1782560000800';
  },
  signFn(intent) {
    return {
      raw: '0xsigned',
      intentHash: intent.hash,
    };
  },
  submitRawTxFn(signedTx) {
    return {
      hash: '0xtxhash',
      raw: signedTx.raw,
    };
  },
}, {
  effect: 'wallet/sign-and-submit',
  intent: {
    id: 'intent:invalid-submit-clock',
    status: 'intent.status/approved',
    accountId: 'acct:main',
    chainId: 1,
    origin: 'https://app.example',
    kind: 'intent.kind/contract-call',
    hash: 'wallet-intent:v1:invalid-submit-clock',
    to: '0xdef0000000000000000000000000000000000000',
    value: '0x0',
    data: '0x',
  },
}), 'invalid submit clock should expose structured runtime error data');
assert(invalidSubmitClock.data.kind === 'wallet.clock/submitted-at',
  'invalid submit clock did not preserve result kind');
assert(invalidSubmitClock.data.field === 'submitted-at' &&
  invalidSubmitClock.data.actual === '1782560000800',
  'invalid submit clock did not preserve field/actual data');

const invalidSignatureClock = expectRuntimeError(() => runWalletEffect({
  clockFn() {
    return 0;
  },
  signMessageFn(intent) {
    return {
      signature: '0xsig',
      payloadHash: intent['payload-hash'],
    };
  },
}, {
  effect: 'wallet/sign-message',
  intent: {
    id: 'intent:invalid-signature-clock',
    status: 'intent.status/approved',
    accountId: 'acct:main',
    chainId: 1,
    origin: 'https://app.example',
    kind: 'intent.kind/message-sign',
    payloadHash: 'payload:invalid-signature-clock',
  },
}), 'invalid signature clock should expose structured runtime error data');
assert(invalidSignatureClock.data.kind === 'wallet.clock/signed-at',
  'invalid signature clock did not preserve result kind');
assert(invalidSignatureClock.data.field === 'signed-at' &&
  invalidSignatureClock.data.actual === 0,
  'invalid signature clock did not preserve field/actual data');

const quote = runWalletEffect({
  clockFn() {
    return 1782560000900;
  },
  quoteFn(request) {
    return {
      provider: 'test-quote',
      router: '0xrouter000000000000000000000000000000000000',
      spender: '0xrouter000000000000000000000000000000000000',
      calldata: '0x1234',
      minAmountOut: '300000000000000',
      deadlineMs: 1782560300000,
      blockNumber: 23000000,
      requestHash: `req:${request['amount-in']}`,
    };
  },
}, {
  effect: 'wallet/quote-swap',
  request: {
    origin: 'https://app.example',
    accountId: 'acct:main',
    chainId: 1,
    fromToken: '0xusdc',
    toToken: '0xweth',
    amountIn: '1000000',
    slippageBps: 50,
  },
});
assert(quote.result['min-amount-out'] === '300000000000000',
  'quote result did not normalize host minAmountOut');
assert(quote.commands[0][0] === 'wallet/quote-observed',
  'quote-swap did not preserve quote-observed command namespace');
assert(quote.commands[0][1]['request-hash'] === 'req:1000000',
  'quote-swap did not preserve normalized request hash');

const asyncQuote = await runWalletEffect({
  clockFn() {
    return 1782560000950;
  },
  quoteFn(request) {
    return Promise.resolve({
      provider: 'async-quote',
      router: '0xrouter000000000000000000000000000000000000',
      spender: '0xrouter000000000000000000000000000000000000',
      calldata: '0x1234',
      minAmountOut: '400000000000000',
      deadlineMs: 1782560300000,
      blockNumber: 23000001,
      requestHash: `async:${request['amount-in']}`,
      chainId: '0x1',
    });
  },
}, {
  effect: 'wallet/quote-swap',
  request: {
    origin: 'https://app.example',
    accountId: 'acct:main',
    chainId: '0x1',
    fromToken: '0xusdc',
    toToken: '0xweth',
    amountIn: '1000000',
    slippageBps: 50,
  },
});
assert(asyncQuote.result.provider === 'async-quote',
  'async quote-swap did not await host quote result');
assert(asyncQuote.result['chain-id'] === 1,
  'async quote-swap did not normalize host quote chainId');
assert(asyncQuote.commands[0][0] === 'wallet/quote-observed',
  'async quote-swap did not preserve quote-observed command namespace');

const invalidQuoteClock = expectRuntimeError(() => runWalletEffect({
  clockFn() {
    return '1782560000900';
  },
  quoteFn(request) {
    return {
      provider: 'test-quote',
      router: '0xrouter000000000000000000000000000000000000',
      spender: '0xrouter000000000000000000000000000000000000',
      calldata: '0x1234',
      minAmountOut: '300000000000000',
      deadlineMs: 1782560300000,
      blockNumber: 23000000,
      requestHash: `bad-clock:${request['amount-in']}`,
    };
  },
}, {
  effect: 'wallet/quote-swap',
  request: {
    origin: 'https://app.example',
    accountId: 'acct:main',
    chainId: 1,
    fromToken: '0xusdc',
    toToken: '0xweth',
    amountIn: '1000000',
    slippageBps: 50,
  },
}), 'invalid quote clock should expose structured runtime error data');
assert(invalidQuoteClock.data.kind === 'wallet.clock/observed-at',
  'invalid quote clock did not preserve result kind');
assert(invalidQuoteClock.data.field === 'observed-at' &&
  invalidQuoteClock.data.actual === '1782560000900',
  'invalid quote clock did not preserve field/actual data');

const sync = runWalletEffect({
  syncFn() {
    return {
      balances: [{
        accountId: 'acct:main',
        chainId: '0x1',
        asset: 'native',
        raw: '42',
        blockNumber: 23000002,
        observedAt: 1782560001000,
      }],
      allowances: [{
        accountId: 'acct:main',
        chainId: '0x1',
        token: '0xusdc',
        spender: '0xrouter000000000000000000000000000000000000',
        amount: '0',
        blockNumber: 23000002,
        observedAt: 1782560001000,
      }],
      receipts: [{
        hash: '0xsync',
        intentId: 'intent:sync',
        confirmedAt: 1782560001001,
        blockNumber: 23000002,
        gasUsed: '31000',
      }],
    };
  },
}, {
  effect: 'wallet/sync',
  request: {
    accountId: 'acct:main',
    chainId: '0x1',
  },
});
assert(sync.commands.map(([command]) => command).join(',') ===
  'wallet/observe-balance,wallet/observe-allowance,wallet/tx-confirmed',
'sync did not materialize balance, allowance, and receipt commands');
assert(sync.commands[0][1]['chain-id'] === 1,
  'runWalletEffect did not normalize sync balance host chainId');
assert(sync.commands[1][1]['chain-id'] === 1,
  'runWalletEffect did not normalize sync allowance host chainId');

const invalidBalanceObservation = expectRuntimeError(() => applyWalletCommands(state, [[
  'wallet/observe-balance',
  {
    accountId: 'acct:main',
    chainId: 1,
    asset: 'native',
    blockNumber: 0,
    raw: '42',
    observedAt: 1782560001000,
  },
]]), 'invalid balance observation should expose structured runtime error data');
assert(invalidBalanceObservation.data.observation === 'balance/observed',
  'invalid balance observation did not preserve observation kind');
assert(invalidBalanceObservation.data.field === 'block-number' &&
  invalidBalanceObservation.data.actual === 0,
  'invalid balance observation did not preserve field/actual data');

const invalidAllowanceObservation = expectRuntimeError(() => applyWalletCommands(state, [[
  'wallet/observe-allowance',
  {
    accountId: 'acct:main',
    chainId: 1,
    token: '0xusdc',
    spender: '0xrouter',
    amount: '0x0',
    blockNumber: 23000002,
    observedAt: 1782560001000,
  },
]]), 'invalid allowance observation should expose structured runtime error data');
assert(invalidAllowanceObservation.data.observation === 'allowance/observed',
  'invalid allowance observation did not preserve observation kind');
assert(invalidAllowanceObservation.data.field === 'amount' &&
  invalidAllowanceObservation.data.actual === '0x0',
  'invalid allowance observation did not preserve field/actual data');

const invalidConfirmedAt = expectRuntimeError(() => applyWalletCommands({
  ...state,
  intents: {
    'intent:bad-confirmed-at': {
      id: 'intent:bad-confirmed-at',
      status: 'intent.status/submitted',
    },
  },
}, [[
  'wallet/tx-confirmed',
  {
    hash: '0xbadconfirmedat',
    intentId: 'intent:bad-confirmed-at',
    blockNumber: 23000002,
    confirmedAt: 0,
  },
]]), 'invalid confirmed-at should expose structured runtime error data');
assert(invalidConfirmedAt.data.observation === 'tx/confirmed',
  'invalid confirmed-at did not preserve observation kind');
assert(invalidConfirmedAt.data.field === 'confirmed-at' &&
  invalidConfirmedAt.data.actual === 0,
  'invalid confirmed-at did not preserve field/actual data');

const invalidSyncReplay = expectRuntimeError(() => applyWalletCommands(state, [[
  'wallet/sync',
  {
    chainId: 0,
    accountId: 'acct:main',
  },
]]), 'invalid sync replay should expose structured runtime error data');
assert(invalidSyncReplay.data.kind === 'wallet.sync/chain-id',
  'invalid sync replay did not preserve result kind');
assert(invalidSyncReplay.data.field === 'chain-id' &&
  invalidSyncReplay.data.actual === 0,
  'invalid sync replay did not preserve field/actual data');

const asyncSync = await runWalletEffect({
  syncFn() {
    return Promise.resolve({
      balances: [{
        accountId: 'acct:main',
        chainId: '0x1',
        asset: 'native',
        raw: '44',
        blockNumber: 23000004,
        observedAt: 1782560003000,
      }],
      allowances: [{
        accountId: 'acct:main',
        chainId: '0x1',
        token: '0xusdc',
        spender: '0xrouter000000000000000000000000000000000000',
        amount: '2',
        blockNumber: 23000004,
        observedAt: 1782560003000,
      }],
    });
  },
}, {
  effect: 'wallet/sync',
  request: {
    accountId: 'acct:main',
    chainId: '0x1',
  },
});
assert(asyncSync.commands.map(([command]) => command).join(',') ===
  'wallet/observe-balance,wallet/observe-allowance',
'async sync did not materialize balance and allowance commands');
assert(asyncSync.commands[0][1]['chain-id'] === 1 &&
  asyncSync.commands[1][1]['chain-id'] === 1,
  'async sync did not normalize host chainId fields');

const synced = applyWalletCommands({
  ...state,
  intents: {
    'intent:sync': {
      id: 'intent:sync',
      status: 'intent.status/submitted',
    },
  },
}, sync.commands);
assert(synced.state.balances['["acct:main" 1 "native"]'].raw === '42',
  'sync replay did not retain native balance');
assert(synced.state.allowances['["acct:main" 1 "0xusdc" "0xrouter000000000000000000000000000000000000"]'] === '0',
  'sync replay did not retain allowance');
assert(synced.state.intents['intent:sync'].status === 'intent.status/confirmed',
  'sync replay did not confirm submitted intent');

const resynced = applyWalletCommands(synced.state, [[
  'wallet/observe-balance',
  {
    accountId: 'acct:main',
    chainId: '0x1',
    asset: 'native',
    raw: '43',
    blockNumber: 23000003,
    observedAt: 1782560002000,
  },
], [
  'wallet/observe-allowance',
  {
    accountId: 'acct:main',
    chainId: '0x1',
    token: '0xusdc',
    spender: '0xrouter000000000000000000000000000000000000',
    amount: '1',
    blockNumber: 23000003,
    observedAt: 1782560002000,
  },
]]);
assert(Object.keys(resynced.state.balances).length === 1 &&
  resynced.state.balances['["acct:main" 1 "native"]'].raw === '43',
  'applyWalletCommands did not round-trip JS balance composite keys');
assert(Object.keys(resynced.state.allowances).length === 1 &&
  resynced.state.allowances['["acct:main" 1 "0xusdc" "0xrouter000000000000000000000000000000000000"]'] === '1',
  'applyWalletCommands did not round-trip JS allowance composite keys');

const allowanceStateProvider = createWalletProvider({
  state: {
    ...state,
    allowances: resynced.state.allowances,
    policies: {
      'https://app.example': {
        ...state.policies['https://app.example'],
        caps: ['eth/accounts', 'eth/chain-id', 'eth/prepare-swap'],
      },
    },
  },
  origin: 'https://app.example',
});
const preparedWithAllowance = await allowanceStateProvider.request({
  method: 'wallet_prepareSwap',
  params: [{
    request: {
      'from-token': '0xusdc',
      'to-token': '0xweth',
      'amount-in': '1',
      'slippage-bps': 50,
    },
    quote: {
      provider: 'test-quote',
      router: '0xrouter000000000000000000000000000000000000',
      spender: '0xrouter000000000000000000000000000000000000',
      calldata: '0x1234',
      'min-amount-out': '1',
      'deadline-ms': 1782560300000,
      'block-number': 23000004,
    },
  }],
});
assert(preparedWithAllowance.length === 1,
  'provider did not round-trip JS allowance composite keys before swap planning');
assert(Object.values(allowanceStateProvider.getState().intents).every((intent) => intent.amount !== '1'),
  'provider created an approval intent despite sufficient round-tripped allowance');

const explicitSwapProvider = createWalletProvider({
  state: {
    ...explicitFromChainState,
    policies: {
      'https://app.example': {
        ...explicitFromChainState.policies['https://app.example'],
        caps: ['eth/accounts', 'eth/chain-id', 'eth/prepare-swap'],
      },
    },
  },
  origin: 'https://app.example',
});
const explicitSwapIds = await explicitSwapProvider.request({
  method: 'wallet_prepareSwap',
  params: [{
    request: {
      from: otherAccount.address,
      chainId: '0x2105',
      'from-token': '0xusdc',
      'to-token': '0xweth',
      'amount-in': '1000000',
      'slippage-bps': 50,
    },
    quote: {
      provider: 'test-quote',
      router: '0xrouter000000000000000000000000000000000000',
      spender: '0xrouter000000000000000000000000000000000000',
      calldata: '0x1234',
      'min-amount-out': '1',
      'deadline-ms': 1782560300000,
      'block-number': 23000005,
    },
  }],
});
assert(explicitSwapIds.length === 2,
  'provider did not create expected swap intents for explicit nested account request');
assert(Object.values(explicitSwapProvider.getState().intents).every((intent) => intent['account-id'] === 'acct:other'),
  'provider did not materialize nested swap from address as the account id');
assert(Object.values(explicitSwapProvider.getState().intents).every((intent) => intent['chain-id'] === 8453),
  'provider did not materialize nested swap chainId before intent creation');

console.log('wallet ESM smoke ok');
