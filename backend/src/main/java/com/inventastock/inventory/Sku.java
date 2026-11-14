package com.inventastock.inventory;

import javax.persistence.Entity;
import javax.persistence.GeneratedValue;
import javax.persistence.GenerationType;
import javax.persistence.Id;
import javax.persistence.Table;

@Entity
@Table(name = "sku")
public class Sku {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  Long id;

  String code;
  String name;
}

