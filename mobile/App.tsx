import React from 'react';
import { StatusBar } from 'expo-status-bar';
import HomeScreen from './src/features/home/HomeScreen';

export default function App() {
  return (
    <>
      <StatusBar style="dark" />
      <HomeScreen />
    </>
  );
}

